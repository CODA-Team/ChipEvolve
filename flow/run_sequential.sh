#!/bin/bash
# run_sequential.sh - Generate config files for parallel runs
#
# For iteration 1: generate random perturbations from base config
# For iteration 2+: load parameters from optimize.py CSV output
#
# Usage: ./run_sequential.sh <platform> <design> <num_runs> <iteration>

set -euo pipefail

if [[ $# -ne 4 ]]; then
    echo "Usage: $0 <platform> <design> <num_runs> <iteration>"
    exit 1
fi

PLATFORM="$1"
DESIGN="$2"
NUM_RUNS="$3"
ITERATION="$4"

# Reproducibility: seed bash's $RANDOM (used below for iter-1 perturbation-based
# config generation) from the campaign seed DRP_SEED (exported by maindriver under
# -S/--seed) + iteration/design. Without this, iter-1 configs are nondeterministic
# even with a fixed --seed, so the whole campaign is not reproducible. DRP_SEED
# unset/"none" -> leave $RANDOM as-is (nondeterministic, previous behaviour).
if [[ -n "${DRP_SEED:-}" && "${DRP_SEED}" != "none" ]]; then
    RANDOM=$(python3 -c "import hashlib,sys;print(int(hashlib.md5('|'.join(sys.argv[1:]).encode()).hexdigest(),16)%32768)" \
             "$DRP_SEED" "$ITERATION" "$PLATFORM" "$DESIGN" 2>/dev/null || echo "$RANDOM")
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# DRP-Agent itself is the flow home (Makefile + scripts/ + platforms/ + designs/
# live here), matching FLOW_HOME used by run_make.sh. The base config.mk here sets
# FASTROUTE_TCL and PRE_GLOBAL_ROUTE_TCL apply the scoped layer adjustments.
FLOW_DIR="$SCRIPT_DIR"
DESIGN_DIR="${SCRIPT_DIR}/designs/${PLATFORM}/${DESIGN}"
CSV_FILE="${DESIGN_DIR}/${PLATFORM}_${DESIGN}.csv"

# Ensure design directory exists
mkdir -p "$DESIGN_DIR"

# Copy base config and SDC from flow if not present
setup_base_files() {
    local flow_design_dir="${FLOW_DIR}/designs/${PLATFORM}/${DESIGN}"

    if [[ ! -f "${DESIGN_DIR}/config.mk" ]]; then
        if [[ -f "${flow_design_dir}/config.mk" ]]; then
            cp "${flow_design_dir}/config.mk" "${DESIGN_DIR}/config.mk"
            echo "Copied base config.mk from flow"
        else
            echo "ERROR: Base config.mk not found at ${flow_design_dir}/config.mk"
            exit 1
        fi
    fi

    # Copy SDC file
    if [[ "$PLATFORM" == "asap7" && "$DESIGN" == "jpeg" ]]; then
        local sdc_name="jpeg_encoder15_7nm.sdc"
    else
        local sdc_name="constraint.sdc"
    fi

    if [[ ! -f "${DESIGN_DIR}/${sdc_name}" ]]; then
        if [[ -f "${flow_design_dir}/${sdc_name}" ]]; then
            cp "${flow_design_dir}/${sdc_name}" "${DESIGN_DIR}/${sdc_name}"
            echo "Copied base ${sdc_name} from flow"
        fi
    fi

    # Copy fastasap.tcl if the design uses it. Needed for routing params to apply.
    if [[ -f "${flow_design_dir}/fastasap.tcl" && ! -f "${DESIGN_DIR}/fastasap.tcl" ]]; then
        cp "${flow_design_dir}/fastasap.tcl" "${DESIGN_DIR}/fastasap.tcl"
        echo "Copied fastasap.tcl from flow"
    fi
}

# Get clock period from SDC file
get_base_clock_period() {
    local sdc_file
    if [[ "$PLATFORM" == "asap7" && "$DESIGN" == "jpeg" ]]; then
        sdc_file="${DESIGN_DIR}/jpeg_encoder15_7nm.sdc"
    else
        sdc_file="${DESIGN_DIR}/constraint.sdc"
    fi

    if [[ -f "$sdc_file" ]]; then
        grep "set clk_period" "$sdc_file" | awk '{print $3}' | head -1
    else
        echo "0"
    fi
}

# Extract a parameter value from config.mk
get_config_param() {
    local config_file="$1"
    local param_name="$2"
    local default_val="$3"

    local val
    val=$(grep -E "^(export\s+)?${param_name}\s*=" "$config_file" 2>/dev/null | \
          sed "s/.*=\s*//" | tr -d ' ' | head -1)

    if [[ -n "$val" ]]; then
        echo "$val"
    else
        echo "$default_val"
    fi
}

# Generate initial random parameters for iteration 1
generate_initial_parameters() {
    local config_file="${DESIGN_DIR}/config.mk"

    # Extract base values
    local synth_flatten
    synth_flatten=$(get_config_param "$config_file" "SYNTH_FLATTEN" "1")
    local core_util
    core_util=$(get_config_param "$config_file" "CORE_UTILIZATION" "40")
    local gp_pad
    gp_pad=$(get_config_param "$config_file" "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT" "2")
    local dp_pad
    dp_pad=$(get_config_param "$config_file" "CELL_PAD_IN_SITES_DETAIL_PLACEMENT" "2")
    local enable_dpo
    enable_dpo=$(get_config_param "$config_file" "ENABLE_DPO" "1")
    local lb_addon
    lb_addon=$(get_config_param "$config_file" "PLACE_DENSITY_LB_ADDON" "0.2")
    local tns_percent
    tns_percent=$(get_config_param "$config_file" "TNS_END_PERCENT" "100")
    local floorplan_pin_adjust
    floorplan_pin_adjust=$(get_config_param "$config_file" "FLOORPLAN_PIN_LAYER_ADJUST" \
        "$(get_config_param "$config_file" "PIN_LAYER_ADJUST" "0.5")")
    local floorplan_above_adjust
    floorplan_above_adjust=$(get_config_param "$config_file" "FLOORPLAN_ABOVE_LAYER_ADJUST" \
        "$(get_config_param "$config_file" "ABOVE_LAYER_ADJUST" "0.5")")
    local clk_period
    clk_period=$(get_base_clock_period)

    # Remove old CSV
    rm -f "$CSV_FILE"

    # Inter-iteration generation is exactly 10-D. CTS and final routing are
    # conditioned on post-place/post-CTS observations later in the flow.
    echo "SYNTH_FLATTEN,CORE_UTILIZATION,CELL_PAD_IN_SITES_GLOBAL_PLACEMENT,CELL_PAD_IN_SITES_DETAIL_PLACEMENT,ENABLE_DPO,PLACE_DENSITY_LB_ADDON,TNS_END_PERCENT,FLOORPLAN_PIN_LAYER_ADJUST,FLOORPLAN_ABOVE_LAYER_ADJUST,clk_period" > "$CSV_FILE"

    # Generate N parameter sets. Run 1 = the un-perturbed BASELINE config (the
    # default config.mk values) so the optimization's best result is guaranteed
    # never worse than baseline: baseline combo == 1.0 by definition and elitism
    # carries it forward. Runs 2..N are random perturbations of it.
    for i in $(seq 1 "$NUM_RUNS"); do
        if [[ "$i" -eq 1 ]]; then
            echo "${synth_flatten},${core_util},${gp_pad},${dp_pad},${enable_dpo},${lb_addon},${tns_percent},${floorplan_pin_adjust},${floorplan_above_adjust},${clk_period}" >> "$CSV_FILE"
            continue
        fi
        local factor
        factor=$(awk -v seed=$RANDOM 'BEGIN{srand(seed); print 0.90 + rand() * 0.20}')

        # Perturb each parameter with constraints
        local new_core_util
        new_core_util=$(awk -v val="$core_util" -v f="$factor" 'BEGIN{
            new=int(val * f); print (new < 20 ? 20 : (new > 99 ? 99 : new))
        }')
        local new_gp_pad
        new_gp_pad=$(awk -v val="$gp_pad" -v seed=$RANDOM 'BEGIN{
            srand(seed); new=int(val + (rand()-0.5)*4);
            print (new < 0 ? 0 : (new > 4 ? 4 : new))
        }')
        local new_dp_pad
        new_dp_pad=$(awk -v val="$dp_pad" -v seed=$RANDOM 'BEGIN{
            srand(seed); new=int(val + (rand()-0.5)*4);
            print (new < 0 ? 0 : (new > 4 ? 4 : new))
        }')
        local new_dpo
        new_dpo=$(awk -v seed=$RANDOM 'BEGIN{srand(seed); print (rand() > 0.5 ? 1 : 0)}')
        local new_lb
        new_lb=$(awk -v val="$lb_addon" -v f="$factor" 'BEGIN{
            new=val * f; printf "%.4f", (new < 0 ? 0 : (new > 0.99 ? 0.99 : new))
        }')
        local new_tns
        new_tns=$(awk -v val="$tns_percent" -v seed=$RANDOM 'BEGIN{
            srand(seed); new=int(val + (rand()-0.5)*40);
            print (new < 0 ? 0 : (new > 100 ? 100 : new))
        }')
        local new_synth
        new_synth=$(awk -v seed=$RANDOM 'BEGIN{srand(seed); print (rand() > 0.5 ? 1 : 0)}')
        local new_pin
        new_pin=$(awk -v val="$floorplan_pin_adjust" -v seed=$RANDOM 'BEGIN{
            srand(seed); new=val + (rand()-0.5)*0.3;
            printf "%.4f", (new < 0.2 ? 0.2 : (new > 0.7 ? 0.7 : new))
        }')
        local new_above
        new_above=$(awk -v val="$floorplan_above_adjust" -v seed=$RANDOM 'BEGIN{
            srand(seed); new=val + (rand()-0.5)*0.3;
            printf "%.4f", (new < 0.2 ? 0.2 : (new > 0.7 ? 0.7 : new))
        }')
        local new_clk
        new_clk=$(awk -v val="$clk_period" -v f="$factor" 'BEGIN{printf "%.2f", val * f}')

        echo "${new_synth},${new_core_util},${new_gp_pad},${new_dp_pad},${new_dpo},${new_lb},${new_tns},${new_pin},${new_above},${new_clk}" >> "$CSV_FILE"
    done

    echo "Generated initial parameters for $NUM_RUNS runs"
}

# Generate config and SDC files from CSV
generate_config_files() {
    local flow_config="${FLOW_DIR}/designs/${PLATFORM}/${DESIGN}/config.mk"
    local default_cts_size
    default_cts_size=$(get_config_param "$flow_config" "CTS_CLUSTER_SIZE" "25")
    local default_cts_diameter
    default_cts_diameter=$(get_config_param "$flow_config" "CTS_CLUSTER_DIAMETER" "100")
    local default_pin_adjust
    default_pin_adjust=$(get_config_param "$flow_config" "PIN_LAYER_ADJUST" "0.5")
    local default_above_adjust
    default_above_adjust=$(get_config_param "$flow_config" "ABOVE_LAYER_ADJUST" "0.5")

    # Remove stale numbered per-run configs/SDCs from a previous run (e.g. when
    # -r was larger before). Keeps the base config.mk / constraint.sdc /
    # fastasap.tcl. Without this, leftover config_5..N.mk pollute the backup and
    # the optimizer's history with phantom (never-run) entries.
    rm -f "${DESIGN_DIR}"/config_[0-9]*.mk "${DESIGN_DIR}"/constraint_[0-9]*.sdc 2>/dev/null || true
    if [[ "$PLATFORM" == "asap7" && "$DESIGN" == "jpeg" ]]; then
        rm -f "${DESIGN_DIR}"/jpeg_encoder15_7nm_[0-9]*.sdc 2>/dev/null || true
    fi

    # Base SDC file
    if [[ "$PLATFORM" == "asap7" && "$DESIGN" == "jpeg" ]]; then
        local base_sdc="${DESIGN_DIR}/jpeg_encoder15_7nm.sdc"
    else
        local base_sdc="${DESIGN_DIR}/constraint.sdc"
    fi

    # NOTE: positional read — field order MUST match the 10-D upstream CSV.
    local i=1
    tail -n +2 "$CSV_FILE" | while IFS=',' read -r synth_flatten core_util gp_pad dp_pad enable_dpo lb_addon tns_percent floorplan_pin_adjust floorplan_above_adjust clk_period; do

        local config_file="${DESIGN_DIR}/config_${i}.mk"

        # SYNTH_FLATTEN is the agent-facing knob (1=flatten, 0=keep hierarchy),
        # but the flow's real variable is SYNTH_HIERARCHICAL with inverted meaning
        # (1=hierarchical, 0=flat). Translate here. SYNTH_FLATTEN itself is a no-op
        # in the flow but kept in config.mk so optimize.py can read it back as history.
        local synth_hier
        synth_hier=$(awk -v v="$synth_flatten" 'BEGIN{f=((v+0)>=0.5)?1:0; print 1-f}')

        # Per-run SDC path (absolute) — defined before the heredoc so it can be
        # written into config_i.mk to override the (relative) SDC_FILE inherited
        # from the included base config.
        if [[ "$PLATFORM" == "asap7" && "$DESIGN" == "jpeg" ]]; then
            local new_sdc="${DESIGN_DIR}/jpeg_encoder15_7nm_${i}.sdc"
        else
            local new_sdc="${DESIGN_DIR}/constraint_${i}.sdc"
        fi

        # Create config that includes flow's base config and overrides.
        # Routing params are set up-front here AND may be re-tuned in the
        # post-CTS DRP stage (which overrides these via update_config_params).
        cat > "$config_file" << CONFIGEOF
# Auto-generated config for run $i (iteration $ITERATION)
# Include base config from flow
include ${flow_config}

# Override synthesis parameters (SYNTH_HIERARCHICAL is the flow's real knob;
# SYNTH_FLATTEN kept only for history extraction by optimize.py)
export SYNTH_FLATTEN = ${synth_flatten}
export SYNTH_HIERARCHICAL = ${synth_hier}

# Override placement parameters
export CORE_UTILIZATION = ${core_util}
export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT = ${gp_pad}
export CELL_PAD_IN_SITES_DETAIL_PLACEMENT = ${dp_pad}
export ENABLE_DPO = ${enable_dpo}
export PLACE_DENSITY_LB_ADDON = ${lb_addon}
export TNS_END_PERCENT = ${tns_percent}
export FLOORPLAN_PIN_LAYER_ADJUST = ${floorplan_pin_adjust}
export FLOORPLAN_ABOVE_LAYER_ADJUST = ${floorplan_above_adjust}

# Safe downstream defaults; post-place DRP replaces these CTS values.
export CTS_CLUSTER_SIZE = ${default_cts_size}
export CTS_CLUSTER_DIAMETER = ${default_cts_diameter}

# Safe downstream defaults; post-CTS DRP replaces only this independent pair.
export PIN_LAYER_ADJUST = ${default_pin_adjust}
export ABOVE_LAYER_ADJUST = ${default_above_adjust}

# Per-run SDC: absolute path overrides the relative SDC_FILE from the base config
export SDC_FILE = ${new_sdc}
CONFIGEOF

        # Create per-run SDC content with modified clock period
        cp "$base_sdc" "$new_sdc"
        # Rewrite atomically without relying on GNU/BSD-specific sed -i syntax.
        awk -v period="$clk_period" '
            BEGIN { print "set clk_period " period }
            !/set[[:space:]]+clk_period/ { print }
        ' "$new_sdc" > "${new_sdc}.tmp"
        mv "${new_sdc}.tmp" "$new_sdc"
        # Ensure Unix line endings
        tr -d '\r' < "$new_sdc" > "${new_sdc}.tmp" && mv "${new_sdc}.tmp" "$new_sdc"

        i=$((i + 1))
        if [[ $i -gt $NUM_RUNS ]]; then
            break
        fi
    done

    echo "Generated $NUM_RUNS config files in ${DESIGN_DIR}"
}

# Main execution
setup_base_files

if [[ "$ITERATION" -eq 1 ]]; then
    # First iteration: generate random parameters
    rm -f "$CSV_FILE"
    generate_initial_parameters
    python3 "$SCRIPT_DIR/initial_constraints.py" "$CSV_FILE" "$PLATFORM" "$DESIGN"
else
    # Subsequent iterations: CSV should already exist from optimize.py
    if [[ ! -f "$CSV_FILE" ]]; then
        echo "ERROR: Expected CSV file $CSV_FILE from optimize.py"
        exit 1
    fi
    echo "Using parameters from optimize.py: $CSV_FILE"
fi

generate_config_files

echo "Sequential phase completed for iteration $ITERATION"

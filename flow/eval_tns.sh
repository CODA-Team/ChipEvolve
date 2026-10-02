#!/bin/bash
# eval_tns.sh - Re-evaluate TNS for all runs under a fixed reference clock CP_0.
#
# Flow:
#   Iteration 1: extract default run's ECP -> CP_0 = ECP * 0.9, save to file,
#                 then evaluate TNS for all (parallel_runs+1) tasks.
#   Iteration 2+: read saved CP_0, evaluate TNS for all parallel_runs tasks.
#
# Usage: ./eval_tns.sh <platform> <design> <parallel_runs> <iteration> [stage]
#   stage: place | cts | final  (default: final) -> which stage ODB to evaluate.
# CP_0 = run_1 (baseline) final ECP * 0.9, computed once (when cp0.txt is missing,
# which only happens at the iter-1 final call) and reused thereafter.

set -euo pipefail

if [ $# -lt 4 ]; then
    echo "Usage: $0 <platform> <design> <parallel_runs> <iteration> [stage]"
    exit 1
fi

platform=$1
design=$2
parallel_runs=$3
iteration=$4
stage=${5:-final}

# Per-stage ODB to evaluate TNS on (canonical ORFS do-copy result ODBs).
case "$stage" in
    place) odb_name="3_place.odb" ;;
    cts)   odb_name="4_cts.odb" ;;
    final) odb_name="6_final.odb" ;;
    *) echo "Error: unknown stage '$stage' (expected place/cts/final)"; exit 1 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLATFORM_DIR="${SCRIPT_DIR}/platforms/${platform}"
CP0_FILE="${SCRIPT_DIR}/designs/${platform}/${design}/cp0.txt"

# Hardcoded CP_0 discount factor
CP0_FACTOR=0.9

# Resolve the OpenROAD executable. The flow uses the full path from env.sh
# (tools/install/OpenROAD/bin/openroad); bare "openroad" is NOT on PATH when
# maindriver invokes this script as a subprocess -> "command not found". Honor an
# already-exported OPENROAD_EXE, else source the project env.sh, else PATH lookup.
if [ -z "${OPENROAD_EXE:-}" ] || ! command -v "${OPENROAD_EXE}" >/dev/null 2>&1; then
    if [ -f "${SCRIPT_DIR}/env.sh" ]; then
        # shellcheck disable=SC1090
        source "${SCRIPT_DIR}/env.sh"
    fi
fi
OPENROAD_EXE="${OPENROAD_EXE:-openroad}"
if ! command -v "${OPENROAD_EXE}" >/dev/null 2>&1 && [ ! -x "${OPENROAD_EXE}" ]; then
    echo "[eval_tns.sh] ERROR: OpenROAD executable not found (OPENROAD_EXE='${OPENROAD_EXE}'). Set it in env.sh."
    exit 1
fi

# --- Determine liberty file glob patterns per platform ---
# Patterns are space-separated, each is a glob expanded inside the Tcl script.
# For asap7: include both compressed (.lib.gz, e.g. AO/INVBUF/OA/SIMPLE) and
# uncompressed (.lib, e.g. SEQ which has the FF cells, and FAKE DFF cells).
# Without the SEQ liberty, FFs in the design have no timing models → STA
# reports 0 registers / 0 paths / TNS = 0.
case "$platform" in
    asap7)
        LIB_FILES="${PLATFORM_DIR}/lib/NLDM/*_RVT_TT_nldm_*.lib.gz ${PLATFORM_DIR}/lib/NLDM/*_RVT_TT_nldm_*.lib ${PLATFORM_DIR}/lib/NLDM/*_SRAM_TT_nldm_*.lib.gz ${PLATFORM_DIR}/lib/NLDM/*_SRAM_TT_nldm_*.lib"
        if [ "$design" == "swerv_wrapper" ]; then
            LIB_FILES="${LIB_FILES} ${SCRIPT_DIR}/designs/${platform}/${design}/lib/*.lib"
        fi
        ;;
    sky130hd)
        # Std cells + dummy IO (some designs reference IO macros)
        LIB_FILES="${PLATFORM_DIR}/lib/sky130_fd_sc_hd__tt_025C_1v80.lib ${PLATFORM_DIR}/lib/sky130_dummy_io.lib"
        ;;
    nangate45)
        # Std cells + all fakeram macro libs (harmless if a design doesn't use them)
        LIB_FILES="${PLATFORM_DIR}/lib/NangateOpenCellLibrary_typical.lib ${PLATFORM_DIR}/lib/fakeram45_*.lib"
        ;;
    *)
        echo "Error: unsupported platform '$platform' for TNS evaluation"
        exit 1
        ;;
esac
export LIB_FILES

# --- Determine base SDC file (used as template for CP_0 SDC) ---
if [[ "$platform" == "asap7" && "$design" == "jpeg" ]]; then
    BASE_SDC="${SCRIPT_DIR}/designs/${platform}/${design}/jpeg_encoder15_7nm.sdc"
else
    BASE_SDC="${SCRIPT_DIR}/designs/${platform}/${design}/constraint.sdc"
fi

# --- Number of tasks: baseline is run_1 (occupies a slot), so always N runs. ---
effective_runs=$parallel_runs

# --- Helper: extract ECP from a run's log ---
# Extract ECP from the "Report metrics stage 6, finish" section of a log file.
# Uses Python with the same regex as optimize.py to ensure consistency.
extract_ecp_from_log() {
    local log_file=$1
    python3 -c "
import re, sys
content = open(sys.argv[1]).read()
# Primary: clock_period_min from stage 6 finish (same regex as optimize.py)
m = re.search(r'Report metrics stage 6, finish[\s\S]*?(?:core_)?cl[ock]*\s+period_min\s*=\s*([-\d.]+)', content)
if m:
    print(m.group(1))
    sys.exit(0)
# Fallback: clock_period - worst_slack from stage 6
p = re.search(r'clock period to\s*([\d.]+)', content)
w = re.search(r'Report metrics stage 6, finish[\s\S]*?wns max\s+([-\d.]+)', content)
if p and w:
    print(f'{float(p.group(1)) - float(w.group(1)):.4f}')
    sys.exit(0)
" "$log_file"
}

# ============================================================
# Step 1: Compute CP_0 on iteration 1
# ============================================================
if [ -f "$CP0_FILE" ]; then
    CP_0=$(cat "$CP0_FILE")
    echo "[eval_tns.sh] Loaded CP_0 = $CP_0 from $CP0_FILE"
else
    # First call (iter-1 final): CP_0 = baseline (run_1) FINAL ECP * 0.9. run_1 is
    # the un-perturbed baseline config; its final ECP only exists at the final stage,
    # which is why CP_0 is computed here (maindriver only calls eval_tns at the final
    # stage on iter1; place/cts iter1 rank by native stage TNS instead).
    default_log="${SCRIPT_DIR}/logs/${platform}_${design}_run1.log"
    if [ ! -f "$default_log" ]; then
        echo "[eval_tns.sh] ERROR: baseline run_1 log not found: $default_log"
        exit 1
    fi
    default_ecp=$(extract_ecp_from_log "$default_log")
    if [ -z "$default_ecp" ]; then
        echo "[eval_tns.sh] ERROR: could not extract ECP from baseline run_1 log"
        exit 1
    fi
    CP_0=$(echo "$default_ecp $CP0_FACTOR" | awk '{printf "%.4f", $1 * $2}')
    echo "$CP_0" > "$CP0_FILE"
    echo "[eval_tns.sh] Baseline(run_1) ECP = $default_ecp, CP_0 = ECP * $CP0_FACTOR = $CP_0 (saved to $CP0_FILE)"
fi

# ============================================================
# Step 2: Determine clock port name (eval_tns.tcl will create the clock
# programmatically rather than reading SDC, since the ODB already has
# a propagated clock that conflicts with read_sdc).
# ============================================================
case "$design" in
    aes|jpeg)  clk_port_name="clk" ;;
    ibex)      clk_port_name="clk_i" ;;
    swerv_wrapper)  clk_port_name="clk" ;; 
    *)
        # Try to extract from the design's SDC
        clk_port_name=$(grep -E '^set clk_port_name' "$BASE_SDC" | awk '{print $3}' | head -1)
        if [ -z "$clk_port_name" ]; then
            echo "[eval_tns.sh] ERROR: Could not determine clock port name for design '$design'"
            exit 1
        fi
        ;;
esac
export CLK_PORT="$clk_port_name"
export CP0="$CP_0"

echo "[eval_tns.sh] Will create clock on port '$clk_port_name' with period $CP_0"

# ============================================================
# Step 3: Evaluate TNS for each run
# ============================================================
echo "[eval_tns.sh] Evaluating TNS for $effective_runs runs under CP_0 = $CP_0 ..."

diag_done=0   # dump key OpenROAD signals for the FIRST actually-evaluated run
n_success=0   # runs that yielded a real CP_0 tns; 0 => whole eval is broken -> exit 1
n_evaluated=0 # runs whose ODB existed and OpenROAD was actually invoked
for ((i=1; i<=effective_runs; i++)); do
    run_dir="${SCRIPT_DIR}/results/${platform}/${design}/run_${i}"
    odb_path="${run_dir}/${odb_name}"
    spef_path="${run_dir}/${odb_name%.odb}.spef"   # may not exist for place/cts; tcl guards
    run_log="${SCRIPT_DIR}/logs/${platform}_${design}_run${i}.log"

    if [ ! -f "$odb_path" ]; then
        echo "[eval_tns.sh] SKIP run $i: ODB not found at $odb_path"
        echo "[TNS_EVAL][${stage}] tns_eval = N/A (odb_missing)" >> "$run_log"
        continue
    fi

    export ODB_PATH="$odb_path"
    export SPEF_PATH="$spef_path"
    n_evaluated=$((n_evaluated + 1))

    echo "[eval_tns.sh] Evaluating run $i (${stage}) ..."
    eval_log="${SCRIPT_DIR}/logs/eval_tns_${stage}_run${i}.log"
    $OPENROAD_EXE -exit "${SCRIPT_DIR}/eval_tns.tcl" > "$eval_log" 2>&1 || true

    # report_tns / report_wns print a line whose first token is 'tns' / 'wns'
    # followed by the value, e.g. "tns 0.00" or "tns -12345.67". Anchor on a line
    # STARTING with tns/wns (so the DEBUG '--- report_tns ---' header is ignored)
    # and pull a signed float that MUST contain a digit (a bare '.' is not a value).
    _float_re='[-+]?[0-9]+\.?[0-9]*([eE][-+]?[0-9]+)?'
    tns_val=$(grep -iE '^[[:space:]]*tns([[:space:]]|$)' "$eval_log" | grep -oE "$_float_re" | tail -1) || true
    wns_val=$(grep -iE '^[[:space:]]*wns([[:space:]]|$)' "$eval_log" | grep -oE "$_float_re" | tail -1) || true
    # report_power "Total" row: "Total  <internal> <switching> <leakage> <total> [%]"
    # -> 5th field = total power (= finish__power__total), evaluated at CP_0.
    power_val=$(awk '$1=="Total"{print $5}' "$eval_log" | tail -1) || true

    # Diagnostic: surface run 1's key OpenROAD signals so the experiment log reveals
    # WHY extraction may fail (0 liberty / 0 registers / clock not set / no paths)
    # and the real report_tns format. Grep targeted lines (report_checks output can
    # otherwise push these past a tail window).
    if [ "$diag_done" -eq 0 ]; then
        diag_done=1
        echo "[eval_tns.sh] (diag) run $i ${stage} key signals -----------------"
        grep -nE "Loaded .* liberty|Register count|Pre-existing clocks|Removing existing|Found clock port|clock port .* not found|Active clocks|Creating clock|Reading SPEF|estimate_parasitics|ERROR|Error|Warning|^tns |^wns |tns max|wns max|[Nn]o paths|report_power|^Total " "$eval_log" | head -45
        echo "[eval_tns.sh] (diag) ----------------------------------------------"
    fi

    if [ -n "$tns_val" ]; then
        echo "[TNS_EVAL][${stage}] tns_eval = $tns_val" >> "$run_log"
        echo "  run $i (${stage}): tns_eval = $tns_val (wns_eval = ${wns_val:-N/A})"
        n_success=$((n_success + 1))
    else
        echo "[TNS_EVAL][${stage}] tns_eval = N/A (extraction_failed)" >> "$run_log"
        echo "  run $i (${stage}): tns_eval extraction failed (raw tns lines: $(grep -i 'tns' "$eval_log" | tr '\n' '|' | tail -c 200))"
    fi
    # Power at CP_0 (used only at the final stage for the power-budget constraint).
    if [ -n "$power_val" ]; then
        echo "[POWER_EVAL][${stage}] power_eval = $power_val" >> "$run_log"
        echo "  run $i (${stage}): power_eval = $power_val W (at CP_0)"
    else
        echo "[POWER_EVAL][${stage}] power_eval = N/A (extraction_failed)" >> "$run_log"
    fi
done

# Zero successful CP_0 evaluations => the whole eval is broken (OpenROAD/liberty/clock
# problem, or no ODBs). Fail LOUDLY (non-zero) so maindriver aborts instead of letting
# extract_metrics silently fall back to native (own-clock) TNS and rank on mixed clocks.
if [ "$n_success" -eq 0 ]; then
    echo "[eval_tns.sh] ERROR: 0/${n_evaluated} evaluated runs produced a CP_0 TNS "\
         "(stage=$stage). Not proceeding with native-TNS fallback." >&2
    exit 1
fi
echo "[eval_tns.sh] CP_0 TNS obtained for ${n_success}/${n_evaluated} evaluated runs."

# ============================================================
# Step 4: derive tns_base = |baseline(run_1) final tns_eval| (once, at final stage).
# ============================================================
TNS_BASE_FILE="${SCRIPT_DIR}/designs/${platform}/${design}/tns_base.txt"
if [ "$stage" == "final" ] && [ ! -f "$TNS_BASE_FILE" ]; then
    default_log="${SCRIPT_DIR}/logs/${platform}_${design}_run1.log"
    default_tns_eval=$(grep -oP '\[TNS_EVAL\]\[final\] tns_eval = \K[-\d.eE+]+' "$default_log" | tail -1) || true
    if [ -n "${default_tns_eval:-}" ]; then
        tns_base=$(echo "$default_tns_eval" | awk '{v=$1; printf "%.4f", (v<0?-v:v)}')
        echo "$tns_base" > "$TNS_BASE_FILE"
        echo "[eval_tns.sh] Baseline(run_1) tns_eval = $default_tns_eval, tns_base = $tns_base (saved)"
    else
        # The baseline's CP_0 TNS is the campaign's reference anchor. Other runs
        # having succeeded does NOT compensate: without run_1's genuine value the
        # penalty scale and the baseline contract are undefined. Fail hard.
        echo "[eval_tns.sh] ERROR: could not extract baseline run_1 final tns_eval; "\
             "baseline is invalid — aborting instead of continuing without tns_base." >&2
        exit 1
    fi
fi

# ============================================================
# Step 5: derive power_base = baseline(run_1) final power at CP_0 (once, at final).
# Reference for the power-budget constraint: candidate power <= (1+budget)*power_base.
# ============================================================
POWER_BASE_FILE="${SCRIPT_DIR}/designs/${platform}/${design}/power_base.txt"
if [ "$stage" == "final" ] && [ ! -f "$POWER_BASE_FILE" ]; then
    default_log="${SCRIPT_DIR}/logs/${platform}_${design}_run1.log"
    default_power_eval=$(grep -oP '\[POWER_EVAL\]\[final\] power_eval = \K[-\d.eE+]+' "$default_log" | tail -1) || true
    if [ -n "${default_power_eval:-}" ]; then
        echo "$default_power_eval" > "$POWER_BASE_FILE"
        echo "[eval_tns.sh] Baseline(run_1) power at CP_0 = $default_power_eval W, power_base saved"
    else
        # Without power_base, _power_base() returns None and the power-budget
        # constraint would be SILENTLY DISABLED for the whole campaign. If the
        # budget is active in drp_config.json this must be fatal; without an
        # active budget the file is unused and a warning suffices.
        pb=$(python3 -c "import json;v=json.load(open('${SCRIPT_DIR}/drp_config.json')).get('power_budget');print('' if v is None else v)" 2>/dev/null || echo "")
        if [ -n "$pb" ]; then
            echo "[eval_tns.sh] ERROR: could not extract baseline run_1 power_eval while "\
                 "power_budget=$pb is active — the constraint would be silently disabled. Aborting." >&2
            exit 1
        fi
        echo "[eval_tns.sh] WARNING: could not extract baseline run_1 power_eval "\
             "(power_budget inactive; power_base unused)."
    fi
fi

echo "[eval_tns.sh] TNS/power evaluation complete (iteration $iteration, stage $stage)."

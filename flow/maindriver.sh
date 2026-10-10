#!/bin/bash
# maindriver.sh - Main orchestrator for DRP-Agent staged optimization
#
# Each iteration:
#   1. Generate configs (run_sequential.sh)
#   2. Run placement stage (run_stage.sh place)
#   3. Extract placement metrics → DRP → generate CTS params
#   4. Run CTS stage (run_stage.sh cts)
#   5. Extract CTS metrics → DRP → generate routing params
#   6. Run route + finish stage (run_stage.sh route_finish)
#   7. Collect final metrics, backup, run optimize.py for next iteration
#
# Usage:
#   ./maindriver.sh -p <platform> -d <design> -o <objective> \
#                   [-i iterations] [-r parallel_runs] [-k num_kill] \
#                   [-t timeout] [--cpus total_cpus] \
#                   [--max-concurrent-runs workers] \
#                   [--weight-wl W1] [--weight-ecp W2]

set -euo pipefail

# ─── Default values ──────────────────────────────────────────────────────────
TOTAL_ITERS=3
PARALLEL_RUNS=10
NUM_KILL=2
TIMEOUT="120m"
TOTAL_CPUS=10
CPUS_PER_RUN=1
MAX_CONCURRENT_RUNS=""  # empty means launch all PARALLEL_RUNS (legacy behavior)
WEIGHT_WL=0.5
WEIGHT_ECP=0.5
SELECTION=elitist
AGENTIC=false  # inter-iteration optimizer: false=optimize.py, true=optimize_agentic.py (ReAct+Critic+generate)
NO_LLM=false  # keep -A numerical Agentic/BO flow, but disable all external LLM requests
PREDICTOR=false  # DRP ranking: true=QoR-comparator score (default promising), false=stage metric
SEED=42  # base RNG seed for reproducibility; "none" => nondeterministic. Threaded to all Python via DRP_SEED.
RESUME=false
FRESH=false  # -F: force-clear derived state (cp0/tns_base/power_base/baseline*) before running.

# Full original invocation, recorded into the campaign manifest for provenance.
ORIG_CMD="$0 $*"

# ─── Parse command line ──────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--platform)    PLATFORM="$2"; shift 2 ;;
        -d|--design)      DESIGN="$2"; shift 2 ;;
        -o|--objective)   OBJECTIVE="$2"; shift 2 ;;
        -i|--iterations)  TOTAL_ITERS="$2"; shift 2 ;;
        -r|--parallel-runs) PARALLEL_RUNS="$2"; shift 2 ;;
        -k|--num-kill)    NUM_KILL="$2"; shift 2 ;;
        -s|--selection)   SELECTION="$2"; shift 2 ;;
        -A|--agentic)     AGENTIC="true"; shift ;;
        -N|--no-llm)      NO_LLM="true"; shift ;;
        -P|--predictor)   PREDICTOR="true"; shift ;;
        -S|--seed)        SEED="$2"; shift 2 ;;
        --resume)         RESUME="true"; shift ;;
        -F|--fresh)       FRESH="true"; shift ;;
        -t|--timeout)     TIMEOUT="$2"; shift 2 ;;
        --cpus)           TOTAL_CPUS="$2"; shift 2 ;;
        --max-concurrent-runs) MAX_CONCURRENT_RUNS="$2"; shift 2 ;;
        --weight-wl)      WEIGHT_WL="$2"; shift 2 ;;
        --weight-ecp)     WEIGHT_ECP="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ─── Validate arguments ─────────────────────────────────────────────────────
if [[ -z "${PLATFORM:-}" || -z "${DESIGN:-}" ]]; then
    echo "Usage: $0 -p <platform> -d <design> [-o objective] [-i iters] [-r runs] [-k kill] [-s selection]"
    echo "  platform: asap7, nangate45, sky130hd"
    echo "  design: aes, ibex, jpeg"
    echo "  objective: wl, ecp, combo (default: ecp)"
    echo "  selection: elitist, gwtw (default: elitist)"
    echo "  -A|--agentic: use optimize_agentic.py (ReAct + TextGrad Critic + generate) for inter-iteration"
    echo "  -N|--no-llm: retain -A numerical Agentic/BO flow but disable external LLM guidance (requires -A)"
    echo "  --max-concurrent-runs N: cap active OpenROAD runs while retaining the -r batch width"
    exit 1
fi

OBJECTIVE="${OBJECTIVE:-ecp}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ─── Argument validation (fail fast, before any expensive stage) ────────────
case "$OBJECTIVE" in
    wl|ecp|combo|TNS_EVAL) ;;
    *) echo "ERROR: objective must be wl, ecp, combo, or TNS_EVAL (got '$OBJECTIVE')" >&2; exit 1 ;;
esac
case "$SELECTION" in
    elitist|gwtw) ;;
    *) echo "ERROR: selection must be elitist or gwtw (got '$SELECTION')" >&2; exit 1 ;;
esac
if [[ "$PREDICTOR" == "true" && "$OBJECTIVE" != "TNS_EVAL" ]]; then
    echo "ERROR: -P/--predictor currently supports only objective TNS_EVAL." >&2
    exit 1
fi
if [[ "$NO_LLM" == "true" && "$AGENTIC" != "true" ]]; then
    echo "ERROR: -N/--no-llm requires -A/--agentic; otherwise this is a plain-optimizer ablation." >&2
    exit 1
fi
_pos_int() {  # name value min
    [[ "$2" =~ ^[0-9]+$ ]] && [[ "$2" -ge "$3" ]] \
        || { echo "ERROR: $1 must be an integer >= $3 (got '$2')" >&2; exit 1; }
}
_pos_int "parallel_runs (-r)" "$PARALLEL_RUNS" 2   # -r 0 divides by zero; -r 1 makes DRP a no-op
_pos_int "iterations (-i)"   "$TOTAL_ITERS"   1
if [[ "$AGENTIC" == "true" && "$TOTAL_ITERS" -gt 1 && "$PARALLEL_RUNS" -lt 3 ]]; then
    echo "ERROR: multi-iteration -A/--agentic requires at least 3 runs: Agent2 reserves two front slots and at least one exploration slot. Use -r 3 or higher." >&2
    exit 1
fi
_pos_int "num_kill (-k)"     "$NUM_KILL"      0
_pos_int "cpus (--cpus)"     "$TOTAL_CPUS"    1
if [[ -z "$MAX_CONCURRENT_RUNS" ]]; then
    MAX_CONCURRENT_RUNS="$PARALLEL_RUNS"
fi
_pos_int "max_concurrent_runs (--max-concurrent-runs)" "$MAX_CONCURRENT_RUNS" 1
if [[ "$MAX_CONCURRENT_RUNS" -gt "$PARALLEL_RUNS" ]]; then
    echo "WARN: max concurrent runs ($MAX_CONCURRENT_RUNS) exceeds parallel runs ($PARALLEL_RUNS); using $PARALLEL_RUNS."
    MAX_CONCURRENT_RUNS="$PARALLEL_RUNS"
fi
if [[ "$OBJECTIVE" == "combo" ]]; then
    python3 "$SCRIPT_DIR/driver_orchestration.py" validate-combo-weights \
        --weight-wl "$WEIGHT_WL" --weight-ecp "$WEIGHT_ECP" || exit 1
fi

# Validate num_kill
if [[ $NUM_KILL -gt $((PARALLEL_RUNS / 2)) ]]; then
    echo "WARN: num_kill ($NUM_KILL) > half of parallel_runs ($PARALLEL_RUNS). Adjusting."
    NUM_KILL=$((PARALLEL_RUNS / 2))
fi

CPUS_PER_RUN=$((TOTAL_CPUS / PARALLEL_RUNS))
if [[ $CPUS_PER_RUN -lt 1 ]]; then
    CPUS_PER_RUN=1
fi

# ─── Setup ───────────────────────────────────────────────────────────────────
cd "$SCRIPT_DIR"

# Make scripts executable
chmod +x run_make.sh run_stage.sh run_sequential.sh eval_tns.sh 2>/dev/null || true

# When -A (agentic) is set, also use the Agent1+Agent2 framework for the INTRA-
# iteration DRP stage-param generation (passed through drp.py to agent.py).
AGENTIC_FLAG=""
if [[ "$AGENTIC" == "true" ]]; then AGENTIC_FLAG="--agentic"; fi
NO_LLM_ARGS=()
LLM_ENABLED=true
if [[ "$NO_LLM" == "true" ]]; then
    NO_LLM_ARGS=(--no-llm)
    LLM_ENABLED=false
fi
# -P: predictor artifacts are explicit so the startup preflight and every DRP child
# validate/use the same files. Arrays avoid quoting bugs in optional CLI arguments.
PREDICTOR_CONFIG="$SCRIPT_DIR/predict_model/example_config.json"
PREDICTOR_CHECKPOINT="$SCRIPT_DIR/predict_model/best_model.pt"
PREDICTOR_RANK_MODE="promising"
PREDICTOR_ARGS=()
if [[ "$PREDICTOR" == "true" ]]; then
    PREDICTOR_RANK_MODE=$(python3 driver_orchestration.py predictor-rank-mode \
        --config drp_config.json) || exit 1
    case "$PREDICTOR_RANK_MODE" in
        promising|kill) ;;
        *) echo "ERROR: predictor rank mode must be 'promising' or 'kill' (got '$PREDICTOR_RANK_MODE')" >&2; exit 1 ;;
    esac
    PREDICTOR_ARGS=(
        --predictor
        --predictor-config "$PREDICTOR_CONFIG"
        --predictor-checkpoint "$PREDICTOR_CHECKPOINT"
        --predictor-rank-mode "$PREDICTOR_RANK_MODE"
    )
fi
# QoR-comparator baseline reference: 'default' (fixed run_1) or 'best' (best full-survivor so far).
PREDICTOR_BASELINE_MODE=$(python3 driver_orchestration.py predictor-baseline-mode \
    --config drp_config.json) || exit 1
case "$PREDICTOR_BASELINE_MODE" in
    default|best) ;;
    *) echo "ERROR: predictor_baseline_mode must be 'default' or 'best' (got '$PREDICTOR_BASELINE_MODE')" >&2; exit 1 ;;
esac

# Export for child scripts
export DRP_SEED="$SEED"   # base seed; each Python process derives its own from (DRP_SEED, DRP_ITER, ...)
if [[ "$NO_LLM" == "true" ]]; then
    export DRP_NO_LLM=1
else
    export DRP_NO_LLM=0
fi
export PLATFORM DESIGN OBJECTIVE PARALLEL_RUNS NUM_KILL WEIGHT_WL WEIGHT_ECP SELECTION

# Logging
LOG_NAME="experiment_${PLATFORM}_${DESIGN}_${OBJECTIVE}_$(date +%m%d_%H%M).log"
exec > >(tee -a "$LOG_NAME") 2>&1

echo "================================================================"
echo "  DRP-Agent Staged Optimization"
echo "================================================================"
echo "Start Time:     $(date)"
echo "Platform:       $PLATFORM"
echo "Design:         $DESIGN"
echo "Objective:      $OBJECTIVE"
echo "Iterations:     $TOTAL_ITERS"
echo "Parallel Runs:  $PARALLEL_RUNS"
echo "DRP Kill Count: $NUM_KILL"
echo "Selection:      $SELECTION"
echo "Agentic Opt:    $AGENTIC"
if [[ "$NO_LLM" == "true" ]]; then
    echo "LLM Guidance:   disabled (--no-llm); numerical Agentic/BO retained"
else
    echo "LLM Guidance:   enabled"
fi
echo "Predictor:      $PREDICTOR"
# Ablation provenance: which arm ranked DRP, and EXACTLY which model weights. The
# checkpoint file gets replaced on retraining, so the SHA256 is what ties a result
# to the weights that produced it.
PRED_SHA=""
PRED_CONFIG_SHA=""
if [[ "$PREDICTOR" == "true" ]]; then
    PRED_CKPT="$PREDICTOR_CHECKPOINT"
    PRED_METADATA=$(python3 driver_orchestration.py predictor-metadata \
        --config "$PREDICTOR_CONFIG" --checkpoint "$PREDICTOR_CHECKPOINT") \
        || { echo "ABORT: cannot read predictor metadata." >&2; exit 1; }
    IFS='|' read -r PRED_CONFIG_SHA PRED_SHA PRED_OBJ PRED_TARGETS <<< "$PRED_METADATA"
    echo "DRP Ranker:     predict_model ($PREDICTOR_RANK_MODE)"
    echo "Pred Config:    $PREDICTOR_CONFIG"
    echo "Config SHA256:  ${PRED_CONFIG_SHA:-missing}"
    echo "Pred Ckpt:      $PRED_CKPT"
    echo "Pred SHA256:    ${PRED_SHA:-missing}"
    echo "Pred TrainObj:  $PRED_OBJ"
    echo "Pred Targets:   $PRED_TARGETS"
    echo "Pred Baseline:  $PREDICTOR_BASELINE_MODE"
else
    echo "DRP Ranker:     stage metric ($OBJECTIVE)"
fi
echo "Seed:           $SEED"
echo "CPUs per Run:   $CPUS_PER_RUN"
echo "Max Concurrent: $MAX_CONCURRENT_RUNS"
echo "Timeout:        $TIMEOUT"
if [[ "$OBJECTIVE" == "combo" ]]; then
    echo "Weight WL:      $WEIGHT_WL"
    echo "Weight ECP:     $WEIGHT_ECP"
fi
echo "================================================================"
echo ""

# Validate imports, config/schema, model state, and checkpoint compatibility before
# spending any placement/CTS/route compute. A missing baseline is intentionally NOT a
# preflight error: a fresh iteration 1 creates it only after the genuine final run.
if [[ "$PREDICTOR" == "true" ]]; then
    echo ">>> Predictor preflight..."
    python3 driver_orchestration.py predictor-preflight \
        --config "$PREDICTOR_CONFIG" --checkpoint "$PREDICTOR_CHECKPOINT" \
        || { echo "ABORT: predictor preflight failed before flow launch." >&2; exit 1; }
fi

# ─── Validate platform/design config (fail fast) ────────────────────────────
# Baseline normalization and the power budget are one validated config lookup.
CONFIG_FIELDS=$(python3 driver_orchestration.py config-info \
    --config drp_config.json --platform "$PLATFORM" --design "$DESIGN") || exit 1
IFS='|' read -r WL_BASE ECP_BASE POWER_BUDGET <<< "$CONFIG_FIELDS"
echo "Baseline: wl_base=$WL_BASE, ecp_base=$ECP_BASE"

START_ITER=1
RESUME_PHASE=-1
PRIOR_COMPLETED=0
if [[ "$RESUME" == "true" && ( "$FRESH" == "true" || "${DRP_EXECUTION_BACKEND:-native}" != "platform" ) ]]; then
    echo "ERROR: --resume requires the platform backend and cannot be combined with -F." >&2
    exit 1
fi
export DRP_CAMPAIGN_OPTIONS="$PLATFORM|$DESIGN|$OBJECTIVE|$TOTAL_ITERS|$PARALLEL_RUNS|$NUM_KILL|$SELECTION|$AGENTIC|$NO_LLM|$PREDICTOR|$SEED|$TIMEOUT|$TOTAL_CPUS|$MAX_CONCURRENT_RUNS|$WEIGHT_WL|$WEIGHT_ECP"
if [[ "${DRP_EXECUTION_BACKEND:-native}" == "platform" ]]; then
    PLATFORM_STATE=$(python3 "$SCRIPT_DIR/platform_campaign.py" root)
    mkdir -p "$PLATFORM_STATE"
    exec 9>"$PLATFORM_STATE/controller.lock"
    flock -n 9 || { echo "ERROR: this campaign has an active controller." >&2; exit 1; }
    if [[ "$RESUME" == "true" ]]; then
        python3 "$SCRIPT_DIR/platform_campaign.py" preflight
    elif [[ -e "$PLATFORM_STATE/campaign.json" ]]; then
        echo "ERROR: state root already owns a campaign; use --resume or a new state root." >&2
        exit 1
    fi
fi
CAMPAIGN_DIR="$SCRIPT_DIR/backup_dir/${PLATFORM}/${DESIGN}"
CAMPAIGN_MANIFEST="$CAMPAIGN_DIR/campaign_manifest.json"
LLM_USAGE_LEDGER="$CAMPAIGN_DIR/llm_usage_events.jsonl"
LLM_USAGE_SUMMARY="$CAMPAIGN_DIR/llm_usage_summary.json"
if [[ "$RESUME" == "true" ]]; then
    RESUME_FIELDS=$(python3 "$SCRIPT_DIR/platform_campaign.py" resume)
    IFS='|' read -r START_ITER RESUME_PHASE PRIOR_COMPLETED CAMPAIGN_ID <<< "$RESUME_FIELDS"
    echo "[platform] resuming same campaign $CAMPAIGN_ID at iteration=$START_ITER after phase=$RESUME_PHASE"
else
# Auto-invalidate stale derived state (cp0/tns_base/power_base/baseline*) when the
# design/objective/base-config fingerprint changes — no more manual file cleanup.
# -F/--fresh forces a clear.
FRESH_FLAG=""; [[ "$FRESH" == "true" ]] && FRESH_FLAG="--fresh"
# No '|| true': if state can't be managed we must NOT silently proceed with possibly
# stale cp0/tns_base/power_base/baseline (that reintroduces the exact footgun).
python3 state.py invalidate "$PLATFORM" "$DESIGN" "$OBJECTIVE" \
    "$WEIGHT_WL" "$WEIGHT_ECP" "$POWER_BUDGET" $FRESH_FLAG \
    || { echo "ERROR: state invalidation failed; aborting to avoid stale derived state." >&2; exit 1; }

# state.py predates the V2 baseline sidecar. If it invalidated/cleared the CSV,
# discard any orphaned metadata so bootstrap cannot later pair new data with stale state.
if [[ "$PREDICTOR" == "true" \
      && ! -f "designs/${PLATFORM}/${DESIGN}/baseline_trajectory.csv" ]]; then
    rm -f "designs/${PLATFORM}/${DESIGN}/baseline_trajectory.meta.json"
fi

# Mid-campaign resume is not implicit. Check the state, manifest, and result dumps:
# an interruption can occur before Phase 7 creates optimization_state.json, and in
# that case checking only the state file would let result_dump_1 be overwritten.
CAMPAIGN_DIR="$SCRIPT_DIR/backup_dir/${PLATFORM}/${DESIGN}"
CAMPAIGN_MANIFEST="$CAMPAIGN_DIR/campaign_manifest.json"
LLM_USAGE_LEDGER="$CAMPAIGN_DIR/llm_usage_events.jsonl"
LLM_USAGE_SUMMARY="$CAMPAIGN_DIR/llm_usage_summary.json"
python3 "$SCRIPT_DIR/driver_orchestration.py" campaign-start-guard \
    --state "designs/${PLATFORM}/${DESIGN}/optimization_state.json" \
    --manifest "$CAMPAIGN_MANIFEST" \
    --backup-dir "$CAMPAIGN_DIR"

# Campaign manifest: pins THIS campaign's identity next to its result_dumps so data
# provenance never has to be reconstructed from file hashes again.
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "none")
mkdir -p "$CAMPAIGN_DIR"
python3 driver_orchestration.py write-manifest \
    --path "$CAMPAIGN_MANIFEST" \
    --platform "$PLATFORM" --design "$DESIGN" --objective "$OBJECTIVE" \
    --seed "$SEED" --iterations "$TOTAL_ITERS" --runs "$PARALLEL_RUNS" \
    --num-kill "$NUM_KILL" --selection "$SELECTION" --agentic "$AGENTIC" \
    --llm-enabled "$LLM_ENABLED" \
    --predictor "$PREDICTOR" --predictor-rank-mode "$PREDICTOR_RANK_MODE" \
    --predictor-baseline-mode "$PREDICTOR_BASELINE_MODE" \
    --predictor-config-sha256 "$PRED_CONFIG_SHA" \
    --predictor-checkpoint-sha256 "$PRED_SHA" --power-budget "$POWER_BUDGET" \
    --weight-wl "$WEIGHT_WL" --weight-ecp "$WEIGHT_ECP" \
    --invocation "$ORIG_CMD" --git-commit "$GIT_COMMIT" --log "$LOG_NAME"

# The event ledger is campaign-scoped and shared by every child process. Install
# finalization only after init succeeds so a failed init cannot masquerade as a
# completed zero-token campaign.
CAMPAIGN_ID=$(python3 "$SCRIPT_DIR/llm_usage.py" init \
    --manifest "$CAMPAIGN_MANIFEST" \
    --ledger "$LLM_USAGE_LEDGER" \
    --summary "$LLM_USAGE_SUMMARY")
fi
export DRP_CAMPAIGN_ID="$CAMPAIGN_ID"
export DRP_LLM_USAGE_FILE="$LLM_USAGE_LEDGER"
CAMPAIGN_EXIT_STATUS="failed"

finalize_campaign_usage() {
    local original_rc=$?
    local status="${CAMPAIGN_EXIT_STATUS:-failed}"
    local completed="${COMPLETED_ITERS:-0}"
    local usage_rc
    trap - EXIT INT TERM

    if [[ "$original_rc" -ne 0 && "$status" != "interrupted" ]]; then
        status="failed"
    fi

    # The finalizer itself must not replace a pre-existing flow failure code. On a
    # successful flow, however, inability to publish an exact/explicit usage summary
    # is a campaign failure rather than a silently missing accounting artifact.
    set +e
    python3 "$SCRIPT_DIR/llm_usage.py" finalize \
        --manifest "$CAMPAIGN_MANIFEST" \
        --ledger "$LLM_USAGE_LEDGER" \
        --summary "$LLM_USAGE_SUMMARY" \
        --status "$status" \
        --exit-code "$original_rc" \
        --completed-iterations "$completed"
    usage_rc=$?
    if [[ "$usage_rc" -ne 0 ]]; then
        echo "ERROR: failed to finalize campaign LLM usage accounting." >&2
        if [[ "$original_rc" -eq 0 ]]; then
            original_rc=$usage_rc
        fi
    fi
    exit "$original_rc"
}

interrupt_campaign() {
    local signal_rc=$1
    CAMPAIGN_EXIT_STATUS="interrupted"
    exit "$signal_rc"
}

trap finalize_campaign_usage EXIT
trap 'interrupt_campaign 130' INT
trap 'interrupt_campaign 143' TERM
echo "[LLM usage] campaign ledger: $LLM_USAGE_LEDGER"
if [[ "${DRP_EXECUTION_BACKEND:-native}" == "platform" && "$RESUME" != "true" ]]; then
    python3 "$SCRIPT_DIR/platform_campaign.py" begin
fi
platform_commit() {
    if [[ "${DRP_EXECUTION_BACKEND:-native}" == "platform" ]]; then
        python3 "$SCRIPT_DIR/platform_campaign.py" commit --iteration "$iter" --phase "$1"
    fi
}


# ─── Stage success gate ─────────────────────────────────────────────────────
# Reports the usable-run count AND enforces a minimum: when fewer than MIN_SUCCESS
# runs produce a valid objective (default max(2, 10% of N)), the stage has ~no signal
# and running the downstream stages/DRP/optimizer on it is wasted compute, so the
# function returns non-zero and the caller aborts the campaign (progress is already
# backed up). An unreadable metrics file is also treated as a failure (returns 2).
# Min runs with a valid objective to proceed. Default: proportional — 10% of the
# population, floor 2 (a 50-run iteration with 1 valid run has no ranking signal).
# Deliberately softer than a 20% hard gate: failure rates are CONFIG-driven, so a
# single bad-proposal iteration is usually recoverable via elitism/penalty learning
# in the next one — abort only when the signal is truly gone. Override via
# MIN_SUCCESS=<n> in the environment for stricter/looser gating.
# Default = max(2, 10% of N). Always <= N since the entry validation enforces
# PARALLEL_RUNS >= 2 (single-run campaigns are rejected — DRP selection is
# meaningless with one run).
_ms_default=$(( PARALLEL_RUNS / 10 > 2 ? PARALLEL_RUNS / 10 : 2 ))
MIN_SUCCESS=${MIN_SUCCESS:-$_ms_default}
if ! [[ "$MIN_SUCCESS" =~ ^[0-9]+$ ]] || [[ "$MIN_SUCCESS" -lt 1 ]] \
   || [[ "$MIN_SUCCESS" -gt "$PARALLEL_RUNS" ]]; then
    echo "ERROR: MIN_SUCCESS must be in 1..PARALLEL_RUNS (got '$MIN_SUCCESS')" >&2; exit 1
fi
echo "[gate] MIN_SUCCESS=$MIN_SUCCESS (of $PARALLEL_RUNS runs per stage)"
check_stage_success() {
    local metrics_json=$1 stage=$2
    # For TNS_EVAL, once CP_0 exists (cp0.txt written at iter-1 final), a run only counts
    # if its TNS came from the CP_0 eval (tns_source==cp0_eval) — a native own-clock TNS
    # fallback (eval_tns partially failed) must NOT be ranked against CP_0 TNS.
    local cp0_flag=()
    if [[ "$OBJECTIVE" == "TNS_EVAL" \
          && -f "designs/${PLATFORM}/${DESIGN}/cp0.txt" ]]; then
        cp0_flag=(--require-cp0)
    fi
    python3 driver_orchestration.py stage-gate \
        --metrics "$metrics_json" --stage "$stage" --objective "$OBJECTIVE" \
        --runs "$PARALLEL_RUNS" --min-success "$MIN_SUCCESS" "${cp0_flag[@]}"
}

# Abort the campaign with a clear message when a stage gate fails.
gate_or_abort() {
    if ! check_stage_success "$1" "$2"; then
        echo "ABORT: stage '$2' produced too few usable runs at iteration ${iter}. "\
             "Check the flow / config / --timeout (progress is in backup_dir)." >&2
        exit 1
    fi
}

# ─── Backup function ────────────────────────────────────────────────────────
create_backup() {
    local iteration=$1
    local backup_dir="./backup_dir/${PLATFORM}/${DESIGN}/result_dump_${iteration}"

    echo "Creating backup for iteration ${iteration}..."
    # A dump is immutable evidence once it exists.  state.py moves an old campaign
    # under campaign_<UTC>/ before this driver starts; seeing this path here instead
    # means an interrupted/duplicate iteration would overwrite evidence, so fail.
    if [[ -e "$backup_dir" ]]; then
        echo "ERROR: refusing to overwrite existing result dump: $backup_dir" >&2
        echo "Use -F to archive the previous campaign before starting a replacement." >&2
        return 1
    fi
    mkdir -p "$backup_dir"

    # Copy config files
    cp "designs/${PLATFORM}/${DESIGN}"/config_*.mk "$backup_dir"/ 2>/dev/null || true

    # Copy every design-local SDC, not just constraint_N.sdc. Config snapshots resolve
    # an archived sibling before a live absolute path, so this is the immutable clock
    # recipe that keeps a historical best from acquiring a later iteration's SDC.
    cp "designs/${PLATFORM}/${DESIGN}"/*.sdc "$backup_dir"/ 2>/dev/null || true

    # Snapshot the campaign references used by the constrained objective and V2
    # comparator. In "best" mode the predictor baseline may change each iteration,
    # so keeping only the live design copy would make an archived DRP decision
    # impossible to reproduce later.
    cp "designs/${PLATFORM}/${DESIGN}"/cp0.txt \
       "designs/${PLATFORM}/${DESIGN}"/tns_base.txt \
       "designs/${PLATFORM}/${DESIGN}"/power_base.txt \
       "designs/${PLATFORM}/${DESIGN}"/baseline_trajectory.csv \
       "designs/${PLATFORM}/${DESIGN}"/baseline_trajectory.meta.json \
       "designs/${PLATFORM}/${DESIGN}"/baseline_best.txt \
       "$backup_dir"/ 2>/dev/null || true
    if [[ -f "designs/${PLATFORM}/${DESIGN}/optimization_state.json" ]]; then
        cp "designs/${PLATFORM}/${DESIGN}/optimization_state.json" \
           "$backup_dir/incoming_batch_state.json"
    fi
    local live_csv="designs/${PLATFORM}/${DESIGN}/${PLATFORM}_${DESIGN}.csv"
    local archived_csv="$backup_dir/input_batch_iter${iteration}.csv"
    if [[ ! -f "$live_csv" ]]; then
        echo "ERROR: executed parameter CSV is missing: $live_csv" >&2
        return 1
    fi
    cp "$live_csv" "$archived_csv"
    python3 driver_orchestration.py validate-archived-csv \
        --csv "$archived_csv" --state "$backup_dir/incoming_batch_state.json" \
        --iteration "$iteration" --runs "$PARALLEL_RUNS"

    # Copy logs — THIS design only. A blanket "cp -r logs/*" pulls in stale
    # OTHER-design logs (e.g. asap7_aes_run*.log left over from a previous aes run),
    # which contaminate the optimizer's backup history with the wrong design's
    # metrics. Copy only this design's combined logs + its per-stage subdir.
    mkdir -p "$backup_dir/logs_dump"
    cp logs/${PLATFORM}_${DESIGN}_run*.log "$backup_dir/logs_dump"/ 2>/dev/null || true
    cp -r logs/${PLATFORM}/${DESIGN} "$backup_dir/logs_dump/" 2>/dev/null || true
    cp logs/eval_tns_final_run*.log "$backup_dir/logs_dump/" 2>/dev/null || true

    # Copy per-run results summary
    for run_id in $(seq 1 "$PARALLEL_RUNS"); do
        local run_res="results/${PLATFORM}/${DESIGN}/run_${run_id}"
        if [[ -d "$run_res" ]]; then
            mkdir -p "$backup_dir/results_dump/run_${run_id}"
            # Copy only final ODB and reports (not all intermediate files)
            cp "$run_res"/*.sdc "$backup_dir/results_dump/run_${run_id}"/ 2>/dev/null || true
        fi
    done

    # Publish the complete eight-file canonical set as one contract. The Python
    # archiver validates the source first and stages every file before publishing,
    # so a missing/unfinalized candidate lifecycle cannot leave a seven-file dump.
    python3 driver_orchestration.py archive-canonical \
        --source-directory tmp --directory "$backup_dir" \
        --iteration "$iteration" \
        --runs "$PARALLEL_RUNS" \
        --manifest "backup_dir/${PLATFORM}/${DESIGN}/campaign_manifest.json"
    cp tmp/cts_params.json tmp/routing_params.json tmp/*_params_provenance.json \
       tmp/sorted_metrics_*.json \
       tmp/agentic_prompts_${PLATFORM}_${DESIGN}.json "$backup_dir"/ 2>/dev/null || true

    echo "Backup created in ${backup_dir}"
}

# Every completed campaign has already archived its per-iteration logs. Empty the live
# log workspace so generic eval_tns_<stage>_runN.log names cannot leak into the next
# platform/design campaign. Failed campaigns retain live logs for diagnosis.
cleanup_campaign_logs() {
    local logs_dir="${SCRIPT_DIR}/logs"
    if [[ "$logs_dir" != "${SCRIPT_DIR}/logs" ]]; then
        echo "ERROR: refusing to clean unexpected logs path: $logs_dir" >&2
        return 1
    fi
    rm -rf -- "$logs_dir"
    mkdir -p -- "$logs_dir"
    echo "Live run logs cleaned after completed campaign: $logs_dir"
}

# Read the next-batch contract written by optimize.py/optimize_agentic.py. The
# first campaign iteration legitimately has no state yet; persisted values are
# validated before they can affect DRP protection or stage mutation behavior.
OPT_STATE_PATH="designs/${PLATFORM}/${DESIGN}/optimization_state.json"
read_iteration_policy() {
    local state_path=$1 expected_iteration=$2
    python3 driver_orchestration.py iteration-policy \
        --state "$state_path" --runs "$PARALLEL_RUNS" \
        --iteration "$expected_iteration" \
        --csv "designs/${PLATFORM}/${DESIGN}/${PLATFORM}_${DESIGN}.csv" \
        --manifest "backup_dir/${PLATFORM}/${DESIGN}/campaign_manifest.json" \
        --platform "$PLATFORM" --design "$DESIGN" --objective "$OBJECTIVE"
}

# ─── Main iteration loop ────────────────────────────────────────────────────
COMPLETED_ITERS=$PRIOR_COMPLETED
EARLY_STOP=false
EARLY_STOP_REASON=""
for iter in $(seq "$START_ITER" "$TOTAL_ITERS"); do
    LAST_PHASE=-1
    if [[ "$iter" -eq "$START_ITER" ]]; then LAST_PHASE=$RESUME_PHASE; fi
    export DRP_ITER="$iter"   # per-iteration seed context for all Python subprocesses

    POLICY_FIELDS=$(read_iteration_policy "$OPT_STATE_PATH" "$iter") \
        || { echo "ABORT: cannot load optimization state for iteration $iter." >&2; exit 1; }
    IFS='|' read -r SEARCH_MODE REPLAY_SLOTS POLICY_STOP POLICY_STOP_REASON POLICY_STATE_ITER <<< "$POLICY_FIELDS"
    export DRP_SEARCH_MODE="$SEARCH_MODE"

    # STOP is terminal inside the active campaign. A separate invocation gets a new
    # manifest id and must use -F; implicit mid-campaign resume is intentionally refused.
    if [[ "$POLICY_STOP" == "1" ]]; then
        EARLY_STOP=true
        EARLY_STOP_REASON="$POLICY_STOP_REASON"
        COMPLETED_ITERS="$POLICY_STATE_ITER"
        echo ">>> Campaign already stopped by optimization policy: $EARLY_STOP_REASON"
        break
    fi

    PROTECTED_RUNS="1"
    if [[ -n "$REPLAY_SLOTS" ]]; then
        PROTECTED_RUNS="${PROTECTED_RUNS},${REPLAY_SLOTS}"
    fi

    # Only a missing iteration-1 baseline may use stage-metric bootstrap. Once a
    # baseline exists, every prediction error (including zero scored runs) is fatal.
    PREDICTOR_BOOTSTRAP_ARGS=()
    if [[ "$PREDICTOR" == "true" && "$iter" -eq 1 \
          && ! -f "designs/${PLATFORM}/${DESIGN}/baseline_trajectory.csv" ]]; then
        PREDICTOR_BOOTSTRAP_ARGS=(--predictor-bootstrap-fallback)
    fi

    # Identity protection for run_1 and every protected replay/probe/control slot at
    # both DRP checkpoints. Slots come from the optimizer's persisted batch plan.
    #   iter 1 : run_1 = the UNPERTURBED DEFAULT config (baseline). CP_0/tns_base/
    #            power_base/baseline trajectory all derive from its genuine final, so
    #            DRP must never overwrite it — and if it FAILS a stage the campaign
    #            aborts loudly (no pseudo-baseline) via --protect-abort-on-fail.
    #   iter 2+: run_1 = the elitism-carried best-so-far replay (optimize/agentic put
    #            the elite at params[0] -> CSV row 1 -> config_1). Protected while
    #            healthy; if it fails, normal failure handling kills it.
    PROTECT_FLAGS=(--protect-runs "$PROTECTED_RUNS")
    if [[ "$iter" -eq 1 ]]; then
        PROTECT_FLAGS+=(--protect-abort-on-fail)
    fi
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  ITERATION $iter of $TOTAL_ITERS"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo "Search Mode:    $DRP_SEARCH_MODE"
    echo "Protected Runs: $PROTECTED_RUNS"
    echo ""

    CANDIDATE_LIFECYCLE="tmp/candidate_lifecycle_iter${iter}.json"
    PLACE_METRICS="tmp/metrics_place_iter${iter}.json"
    CTS_METRICS="tmp/metrics_cts_iter${iter}.json"
    FINAL_METRICS="tmp/metrics_final_iter${iter}.json"
    if [[ "$LAST_PHASE" -lt 0 ]]; then
    # ─── Clean up previous iteration residuals ──────────────────────
    echo ">>> Cleaning up previous run residuals..."
    rm -f logs/${PLATFORM}_${DESIGN}_run*.log
    rm -rf results/${PLATFORM}/${DESIGN}/run_*
    rm -rf objects/${PLATFORM}/${DESIGN}/run_*
    rm -rf reports/${PLATFORM}/${DESIGN}/run_*
    rm -rf logs/${PLATFORM}/${DESIGN}/run_*

    # ─── Phase 0: Generate configs ────────────────────────────────────
    echo ">>> Phase 0: Generating configurations..."
    ./run_sequential.sh "$PLATFORM" "$DESIGN" "$PARALLEL_RUNS" "$iter"

    # Bind the exact numeric CSV rows to stable candidate identities. Iteration 1 is
    # generated by run_sequential itself; later lifecycles are created by the optimizer
    # before it commits the next-batch CSV. Metadata stays in this JSON sidecar and is
    # never added to the 12-column flow CSV.
    CANDIDATE_LIFECYCLE="tmp/candidate_lifecycle_iter${iter}.json"
    INPUT_BATCH_CSV="designs/${PLATFORM}/${DESIGN}/${PLATFORM}_${DESIGN}.csv"
    python3 "$SCRIPT_DIR/driver_orchestration.py" bind-candidates \
        --lifecycle "$CANDIDATE_LIFECYCLE" \
        --csv "$INPUT_BATCH_CSV" \
        --manifest "backup_dir/${PLATFORM}/${DESIGN}/campaign_manifest.json" \
        --iteration "$iter" \
        --runs "$PARALLEL_RUNS"

    # A static replay may need the source lineage's floorplan routing context while
    # retaining the child routing values in the normal CSV. Materialize only these
    # explicitly scoped variables after config generation and record an auditable
    # receipt even when this iteration has no replay slots.
    CONFIG_REPLAY_RECEIPT="tmp/config_replay_iter${iter}.json"
    python3 config_replay.py materialize \
        --state "$OPT_STATE_PATH" \
        --config-dir "designs/${PLATFORM}/${DESIGN}" \
        --output "$CONFIG_REPLAY_RECEIPT" \
        --iteration "$iter" \
        --num-runs "$PARALLEL_RUNS" \
        --platform "$PLATFORM" \
        --design "$DESIGN" \
        --objective "$OBJECTIVE" \
        --manifest "backup_dir/${PLATFORM}/${DESIGN}/campaign_manifest.json" \
        || { echo "ABORT: config replay materialization failed at iteration $iter." >&2; exit 1; }

    platform_commit 0
    fi
    if [[ "$LAST_PHASE" -lt 1 ]]; then
    # ─── Phase 1: Placement stage ─────────────────────────────────────
    echo ""
    echo ">>> Phase 1: Running PLACEMENT stage..."
    timeout "$TIMEOUT" ./run_stage.sh "$PLATFORM" "$DESIGN" "$PARALLEL_RUNS" "place" "$CPUS_PER_RUN" "$MAX_CONCURRENT_RUNS" || true

    # TNS_EVAL: re-evaluate place-stage TNS at the fixed CP_0. On iter1 CP_0 is not
    # known yet (baseline run_1 is not routed) -> skip; extract_metrics then falls
    # back to each run's native place-stage TNS for ranking.
    if [[ "$OBJECTIVE" == "TNS_EVAL" && "$iter" -gt 1 ]]; then
        ./eval_tns.sh "$PLATFORM" "$DESIGN" "$PARALLEL_RUNS" "$iter" place \
            || { echo "ABORT: CP_0 TNS evaluation (place) failed at iter $iter; refusing to rank on native/own-clock TNS." >&2; exit 1; }
    fi

    platform_commit 1
    fi
    if [[ "$LAST_PHASE" -lt 2 ]]; then
    # ─── Phase 2: Post-placement DRP ──────────────────────────────────
    echo ""
    echo ">>> Phase 2: Post-placement DRP..."

    # Extract placement metrics
    PLACE_METRICS="tmp/metrics_place_iter${iter}.json"
    mkdir -p tmp
    # TNS_EVAL + CP_0 established -> only genuine CP_0 evals may carry TNS_EVAL
    REQ_CP0_FLAG=""
    [[ "$OBJECTIVE" == "TNS_EVAL" && -f "designs/${PLATFORM}/${DESIGN}/cp0.txt" ]] && REQ_CP0_FLAG="--require-cp0-tns"
    python3 extract_metrics.py \
        --log-dir ./logs \
        --platform "$PLATFORM" \
        --design "$DESIGN" \
        --num-runs "$PARALLEL_RUNS" \
        --stage place \
        --wl-base "$WL_BASE" \
        --ecp-base "$ECP_BASE" \
        --weight-wl "$WEIGHT_WL" \
        --weight-ecp "$WEIGHT_ECP" \
        $REQ_CP0_FLAG \
        --output "$PLACE_METRICS"

    echo "Placement metrics extracted → $PLACE_METRICS"
    gate_or_abort "$PLACE_METRICS" "place"

    # Run DRP
    DRP_PLACE_RESULT="tmp/drp_place_iter${iter}.json"
    python3 drp.py \
        --stage place \
        --next-stage cts \
        --metrics-file "$PLACE_METRICS" \
        --objective "$OBJECTIVE" \
        --num-kill "$NUM_KILL" \
        --selection "$SELECTION" \
        --platform "$PLATFORM" \
        --design "$DESIGN" \
        --work-dir "$SCRIPT_DIR" \
        --config-dir "designs/${PLATFORM}/${DESIGN}" \
        $AGENTIC_FLAG \
        ${NO_LLM_ARGS[@]+"${NO_LLM_ARGS[@]}"} \
        ${PREDICTOR_ARGS[@]+"${PREDICTOR_ARGS[@]}"} \
        ${PREDICTOR_BOOTSTRAP_ARGS[@]+"${PREDICTOR_BOOTSTRAP_ARGS[@]}"} \
        "${PROTECT_FLAGS[@]}" \
        --candidate-lifecycle "$CANDIDATE_LIFECYCLE" \
        --output "$DRP_PLACE_RESULT"

    platform_commit 2
    fi
    if [[ "$LAST_PHASE" -lt 3 ]]; then
    # ─── Phase 3: CTS stage ───────────────────────────────────────────
    echo ""
    echo ">>> Phase 3: Running CTS stage..."
    timeout "$TIMEOUT" ./run_stage.sh "$PLATFORM" "$DESIGN" "$PARALLEL_RUNS" "cts" "$CPUS_PER_RUN" "$MAX_CONCURRENT_RUNS" || true

    # TNS_EVAL: re-evaluate cts-stage TNS at CP_0 (iter2+; iter1 uses native TNS).
    if [[ "$OBJECTIVE" == "TNS_EVAL" && "$iter" -gt 1 ]]; then
        ./eval_tns.sh "$PLATFORM" "$DESIGN" "$PARALLEL_RUNS" "$iter" cts \
            || { echo "ABORT: CP_0 TNS evaluation (cts) failed at iter $iter; refusing to rank on native/own-clock TNS." >&2; exit 1; }
    fi

    platform_commit 3
    fi
    if [[ "$LAST_PHASE" -lt 4 ]]; then
    # ─── Phase 4: Post-CTS DRP ────────────────────────────────────────
    echo ""
    echo ">>> Phase 4: Post-CTS DRP..."

    # Extract CTS metrics
    CTS_METRICS="tmp/metrics_cts_iter${iter}.json"
    # TNS_EVAL + CP_0 established -> only genuine CP_0 evals may carry TNS_EVAL
    REQ_CP0_FLAG=""
    [[ "$OBJECTIVE" == "TNS_EVAL" && -f "designs/${PLATFORM}/${DESIGN}/cp0.txt" ]] && REQ_CP0_FLAG="--require-cp0-tns"
    python3 extract_metrics.py \
        --log-dir ./logs \
        --platform "$PLATFORM" \
        --design "$DESIGN" \
        --num-runs "$PARALLEL_RUNS" \
        --stage cts \
        --wl-base "$WL_BASE" \
        --ecp-base "$ECP_BASE" \
        --weight-wl "$WEIGHT_WL" \
        --weight-ecp "$WEIGHT_ECP" \
        $REQ_CP0_FLAG \
        --output "$CTS_METRICS"

    echo "CTS metrics extracted → $CTS_METRICS"
    gate_or_abort "$CTS_METRICS" "cts"

    # Run DRP
    DRP_CTS_RESULT="tmp/drp_cts_iter${iter}.json"
    python3 drp.py \
        --stage cts \
        --next-stage routing \
        --metrics-file "$CTS_METRICS" \
        --objective "$OBJECTIVE" \
        --num-kill "$NUM_KILL" \
        --selection "$SELECTION" \
        --platform "$PLATFORM" \
        --design "$DESIGN" \
        --work-dir "$SCRIPT_DIR" \
        --config-dir "designs/${PLATFORM}/${DESIGN}" \
        $AGENTIC_FLAG \
        ${NO_LLM_ARGS[@]+"${NO_LLM_ARGS[@]}"} \
        ${PREDICTOR_ARGS[@]+"${PREDICTOR_ARGS[@]}"} \
        ${PREDICTOR_BOOTSTRAP_ARGS[@]+"${PREDICTOR_BOOTSTRAP_ARGS[@]}"} \
        "${PROTECT_FLAGS[@]}" \
        --candidate-lifecycle "$CANDIDATE_LIFECYCLE" \
        --output "$DRP_CTS_RESULT"

    platform_commit 4
    fi
    if [[ "$LAST_PHASE" -lt 5 ]]; then
    # ─── Phase 5: Route + Finish stage ────────────────────────────────
    echo ""
    echo ">>> Phase 5: Running ROUTE + FINISH stage..."
    timeout "$TIMEOUT" ./run_stage.sh "$PLATFORM" "$DESIGN" "$PARALLEL_RUNS" "route_finish" "$CPUS_PER_RUN" "$MAX_CONCURRENT_RUNS" || true

    # TNS_EVAL: on iter1 this is where CP_0 = baseline(run_1) ECP * 0.9 is computed
    # (run_1 is now routed) and saved to cp0.txt; then evaluate final-stage TNS at
    # CP_0 for every run. From iter2+ CP_0 is reused. objective = |TNS|.
    if [[ "$OBJECTIVE" == "TNS_EVAL" ]]; then
        ./eval_tns.sh "$PLATFORM" "$DESIGN" "$PARALLEL_RUNS" "$iter" final \
            || { echo "ABORT: CP_0 TNS evaluation (final) failed at iter $iter; refusing to rank on native/own-clock TNS." >&2; exit 1; }
    fi

    platform_commit 5
    fi
    if [[ "$LAST_PHASE" -lt 6 ]]; then
    # ─── Phase 6: Final metrics collection ────────────────────────────
    echo ""
    echo ">>> Phase 6: Collecting final metrics..."

    FINAL_METRICS="tmp/metrics_final_iter${iter}.json"
    # TNS_EVAL + CP_0 established -> only genuine CP_0 evals may carry TNS_EVAL
    REQ_CP0_FLAG=""
    [[ "$OBJECTIVE" == "TNS_EVAL" && -f "designs/${PLATFORM}/${DESIGN}/cp0.txt" ]] && REQ_CP0_FLAG="--require-cp0-tns"
    python3 extract_metrics.py \
        --log-dir ./logs \
        --platform "$PLATFORM" \
        --design "$DESIGN" \
        --num-runs "$PARALLEL_RUNS" \
        --stage final \
        --wl-base "$WL_BASE" \
        --ecp-base "$ECP_BASE" \
        --weight-wl "$WEIGHT_WL" \
        --weight-ecp "$WEIGHT_ECP" \
        $REQ_CP0_FLAG \
        --output "$FINAL_METRICS"
    python3 candidate_tracking.py finalize \
        --lifecycle "$CANDIDATE_LIFECYCLE" \
        --metrics "$FINAL_METRICS" \
        --config-dir "designs/${PLATFORM}/${DESIGN}" \
        --strict \
        || { echo "ABORT: candidate lifecycle finalization failed at iteration $iter." >&2; exit 1; }
    gate_or_abort "$FINAL_METRICS" "final"

    # Baseline FINAL validity (iter 1 only). DRP protection keeps run_1 alive through
    # place/cts, but a route/finish failure is swallowed per-run by run_stage's
    # '|| true' — so verify here that run_1 actually produced a valid final objective
    # (and, for TNS_EVAL, a genuine CP_0 eval + power when the budget is active).
    # Without it the campaign has no genuine baseline -> abort, don't fake one.
    if [[ "$iter" -eq 1 ]]; then
        python3 "$SCRIPT_DIR/driver_orchestration.py" baseline-final-check \
            --metrics "$FINAL_METRICS" \
            --objective "$OBJECTIVE" \
            --power-budget "$POWER_BUDGET"
    fi

    # Predictor baseline (mode=default): save run_1's full trajectory only after
    # its final objective/power has passed the genuine-baseline check above. This
    # prevents a failed iteration 1 from leaving a seemingly valid stale baseline.
    if [[ "$PREDICTOR" == "true" && "$PREDICTOR_BASELINE_MODE" == "default" && "$iter" -eq 1 ]]; then
        python3 "$SCRIPT_DIR/driver_orchestration.py" predictor-baseline-create \
            --work-dir "$SCRIPT_DIR" \
            --platform "$PLATFORM" \
            --design "$DESIGN" \
            --config "$PREDICTOR_CONFIG" \
            --checkpoint "$PREDICTOR_CHECKPOINT"
    fi

    # Predictor baseline (mode=best): update baseline_trajectory.csv to the best
    # FULL-SURVIVOR run's trajectory so far (needs this iter's final metrics + DRP
    # victim lists). Restores comparator discrimination once runs beat the default.
    if [[ "$PREDICTOR" == "true" && "$PREDICTOR_BASELINE_MODE" == "best" ]]; then
        python3 "$SCRIPT_DIR/driver_orchestration.py" predictor-baseline-update \
            --work-dir "$SCRIPT_DIR" \
            --platform "$PLATFORM" \
            --design "$DESIGN" \
            --iteration "$iter" \
            --objective "$OBJECTIVE" \
            --config "$PREDICTOR_CONFIG" \
            --checkpoint "$PREDICTOR_CHECKPOINT"
    fi

    echo "Final metrics:"
    python3 "$SCRIPT_DIR/driver_orchestration.py" final-metrics-report \
        --metrics "$FINAL_METRICS" \
        --objective "$OBJECTIVE" \
        --power-budget "$POWER_BUDGET" \
        --platform "$PLATFORM" \
        --design "$DESIGN"

    # ─── Backup ───────────────────────────────────────────────────────
    create_backup "$iter"

    platform_commit 6
    fi
    if [[ "$LAST_PHASE" -lt 7 ]]; then
    # ─── Phase 7: Update policy state / generate the next batch ───────
    echo ""
    # The final iteration still updates observed-vs-clean best and the terminal
    # state, but does not spend time generating a CSV that will never be executed.
    if [[ "$AGENTIC" == "true" ]]; then
        OPT_SCRIPT="optimize_agentic.py"
    else
        OPT_SCRIPT="optimize.py"
    fi
    STATE_ONLY_FLAG=""
    if [[ $iter -ge $TOTAL_ITERS ]]; then
        STATE_ONLY_FLAG="--state-only"
        echo ">>> Phase 7: Persisting final optimization state ($OPT_SCRIPT)..."
    else
        echo ">>> Phase 7: Generating parameters for next iteration ($OPT_SCRIPT)..."
    fi
    python3 "$OPT_SCRIPT" \
        "$PLATFORM" "$DESIGN" "$OBJECTIVE" "$PARALLEL_RUNS" \
        --iteration "$iter" \
        --total-iterations "$TOTAL_ITERS" \
        --weight-wl "$WEIGHT_WL" \
        --weight-ecp "$WEIGHT_ECP" \
        --work-dir "$SCRIPT_DIR" \
        ${NO_LLM_ARGS[@]+"${NO_LLM_ARGS[@]}"} \
        $STATE_ONLY_FLAG

    # create_backup runs before optimization so its history is available to the
    # optimizer. Refresh the state afterwards so every dump, including the final
    # one, records the bests and decision derived from that iteration.
    if [[ -f "$OPT_STATE_PATH" ]]; then
        cp "$OPT_STATE_PATH" \
           "backup_dir/${PLATFORM}/${DESIGN}/result_dump_${iter}/optimization_state.json"

        STOP_FIELDS=$(python3 "$SCRIPT_DIR/driver_orchestration.py" stop-fields \
            --state "$OPT_STATE_PATH") \
            || { echo "ABORT: cannot read optimizer stop state after iteration $iter." >&2; exit 1; }
        IFS='|' read -r STOP_REQUESTED STOP_REASON <<< "$STOP_FIELDS"
        if [[ "$STOP_REQUESTED" == "1" ]]; then
            if [[ $iter -lt $TOTAL_ITERS ]]; then
                EARLY_STOP=true
                EARLY_STOP_REASON="$STOP_REASON"
            else
                echo ">>> Optimization policy reached STOP at the planned final iteration: $STOP_REASON"
            fi
        fi
    else
        echo "ABORT: optimizer produced no optimization_state.json; batch contract is missing." >&2
        exit 1
    fi

    # Phase 7 may invoke Agent1/2/3, so publish the immutable iteration usage view
    # only after it returns and before an early-stop decision can leave the loop.
    python3 "$SCRIPT_DIR/llm_usage.py" snapshot \
        --manifest "$CAMPAIGN_MANIFEST" \
        --ledger "$LLM_USAGE_LEDGER" \
        --summary "$LLM_USAGE_SUMMARY" \
        --iteration "$iter" \
        --output "$CAMPAIGN_DIR/result_dump_${iter}/llm_usage_iter${iter}.json"

    platform_commit 7
    fi
    COMPLETED_ITERS=$iter
    echo ""
    echo ">>> Iteration $iter complete."
    if [[ "$EARLY_STOP" == "true" ]]; then
        echo ">>> Early stop requested after iteration $iter: $EARLY_STOP_REASON"
        break
    fi
done

# ─── Final summary ───────────────────────────────────────────────────────────
echo ""
echo "================================================================"
if [[ "$EARLY_STOP" == "true" ]]; then
    echo "  Early stop after $COMPLETED_ITERS of $TOTAL_ITERS iterations."
    echo "  Reason: $EARLY_STOP_REASON"
else
    echo "  All $COMPLETED_ITERS iterations complete!"
fi
echo "  End Time: $(date)"
echo "================================================================"
echo ""
echo "Results backed up in: backup_dir/${PLATFORM}/${DESIGN}/"
echo "Experiment log: $LOG_NAME"
cleanup_campaign_logs
if [[ "$EARLY_STOP" == "true" ]]; then
    CAMPAIGN_EXIT_STATUS="early_stop"
else
    CAMPAIGN_EXIT_STATUS="completed"
fi

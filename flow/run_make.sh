#!/bin/bash
# run_make.sh - Per-run make wrapper for staged execution
#
# Runs a specific Make target for a single run with isolated directories.
# Uses the flow's Makefile via `make -C` with DRP-Agent-local output dirs.
#
# Usage: ./run_make.sh <config_file> <task_id> <platform> <design> <stage>
#   stage: "place", "cts", "route", "finish", "all"

set -euo pipefail

if [[ $# -lt 5 ]]; then
    echo "Usage: $0 <config_file> <task_id> <platform> <design> <stage>"
    exit 1
fi

CURRENT_CONFIG="$1"
TASK_ID="$2"
PLATFORM="$3"
DESIGN="$4"
STAGE="$5"

# Resolve paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FLOW_DIR="$SCRIPT_DIR"
WORK_DIR="$SCRIPT_DIR"

case "${DRP_EXECUTION_BACKEND:-native}" in
    platform)
        exec python3 "${SCRIPT_DIR}/platform_leaf.py" \
            "$CURRENT_CONFIG" "$TASK_ID" "$PLATFORM" "$DESIGN" "$STAGE"
        ;;
    native) ;;
    *) echo "Unknown execution backend: $DRP_EXECUTION_BACKEND" >&2; exit 1 ;;
esac

# Per-run isolated directories
BASE_PATH="${PLATFORM}/${DESIGN}/run_${TASK_ID}"
RES_DIR="${WORK_DIR}/results/${BASE_PATH}"
LOG_DIR="${WORK_DIR}/logs/${BASE_PATH}"
OBJ_DIR="${WORK_DIR}/objects/${BASE_PATH}"
REP_DIR="${WORK_DIR}/reports/${BASE_PATH}"

mkdir -p "$RES_DIR" "$LOG_DIR" "$OBJ_DIR" "$REP_DIR"

# Resolve config to absolute path
if [[ ! "$CURRENT_CONFIG" = /* ]]; then
    CURRENT_CONFIG="${WORK_DIR}/${CURRENT_CONFIG}"
fi

# Map stage name to Make target
case "$STAGE" in
    place)
        MAKE_TARGET="place"
        ;;
    cts)
        MAKE_TARGET="cts"
        ;;
    route)
        MAKE_TARGET="route"
        ;;
    finish)
        MAKE_TARGET="finish"
        ;;
    route_finish)
        # Route through finish in one go
        MAKE_TARGET="finish"
        ;;
    all)
        MAKE_TARGET=""
        ;;
    clean)
        MAKE_TARGET="clean_all"
        ;;
    *)
        echo "Unknown stage: $STAGE"
        exit 1
        ;;
esac

# Common make arguments
# Pin FLOW_HOME to FLOW_DIR so the Makefile rules AND the tcl scripts/platforms
# both come from the same flow. Otherwise an inherited FLOW_HOME from the shell
# (e.g. OpenROAD-MLOps/env.sh) leaks in and SCRIPTS_DIR/PLATFORM_HOME/DESIGN_HOME
# resolve to a different flow version → synth(.v) vs floorplan(.odb) mismatch.
MAKE_ARGS=(
    -C "$FLOW_DIR"
    FLOW_HOME="$FLOW_DIR"
    DESIGN_CONFIG="$CURRENT_CONFIG"
    RESULTS_DIR="$RES_DIR"
    LOG_DIR="$LOG_DIR"
    OBJECTS_DIR="$OBJ_DIR"
    REPORTS_DIR="$REP_DIR"
    WORK_HOME="$WORK_DIR"
)

# For initial "place" stage on a fresh run, clean first
if [[ "$STAGE" == "place" && ! -f "$RES_DIR/1_synth.v" ]]; then
    make "${MAKE_ARGS[@]}" clean_all 2>/dev/null || true
fi

# Run make with the target
if [[ -n "$MAKE_TARGET" ]]; then
    echo "[Run $TASK_ID] Starting stage: $STAGE (target: $MAKE_TARGET)"
    make "${MAKE_ARGS[@]}" "$MAKE_TARGET"
else
    echo "[Run $TASK_ID] Running full flow"
    make "${MAKE_ARGS[@]}"
fi

echo "[Run $TASK_ID] Stage $STAGE completed"

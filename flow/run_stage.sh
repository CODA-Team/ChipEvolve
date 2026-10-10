#!/bin/bash
# run_stage.sh - Run a specific stage for all parallel runs
#
# Usage: ./run_stage.sh <platform> <design> <num_runs> <stage> \
#                       [cpus_per_run] [max_concurrent_runs]
#   stage: "place", "cts", "route_finish"

set -euo pipefail

if [[ $# -lt 4 ]]; then
    echo "Usage: $0 <platform> <design> <num_runs> <stage> [cpus_per_run] [max_concurrent_runs]"
    exit 1
fi

PLATFORM="$1"
DESIGN="$2"
NUM_RUNS="$3"
STAGE="$4"
CPUS_PER_RUN="${5:-2}"
MAX_CONCURRENT_RUNS="${6:-$NUM_RUNS}"

if ! [[ "$NUM_RUNS" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: num_runs must be a positive integer (got '$NUM_RUNS')" >&2
    exit 1
fi
if ! [[ "$CPUS_PER_RUN" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: cpus_per_run must be a positive integer (got '$CPUS_PER_RUN')" >&2
    exit 1
fi
if ! [[ "$MAX_CONCURRENT_RUNS" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: max_concurrent_runs must be a positive integer (got '$MAX_CONCURRENT_RUNS')" >&2
    exit 1
fi
if [[ "$MAX_CONCURRENT_RUNS" -gt "$NUM_RUNS" ]]; then
    MAX_CONCURRENT_RUNS="$NUM_RUNS"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Create log directories
mkdir -p "${SCRIPT_DIR}/logs"

echo ""
echo "============================================================"
echo "Running stage: $STAGE for $NUM_RUNS parallel runs"
echo "Platform: $PLATFORM | Design: $DESIGN"
echo "CPUs per run: $CPUS_PER_RUN"
echo "Max concurrent runs: $MAX_CONCURRENT_RUNS"
echo "============================================================"
echo ""

# Track worker PIDs and per-run exit codes for bounded parallel execution.
WORKER_PIDS=()
FAILED_RUNS=()
STATUS_DIR=$(mktemp -d "${TMPDIR:-/tmp}/drp-run-stage.XXXXXX")
cleanup_status() {
    rm -rf "$STATUS_DIR"
}
trap cleanup_status EXIT

run_task() {
    local task_id=$1
    local start_cpu=$2
    local end_cpu=$3

    local config_file="${SCRIPT_DIR}/designs/${PLATFORM}/${DESIGN}/config_${task_id}.mk"
    local log_file="${SCRIPT_DIR}/logs/${PLATFORM}_${DESIGN}_run${task_id}.log"

    if [[ ! -f "$config_file" ]]; then
        echo "[WARN] Config file not found: $config_file"
        return 1
    fi

    echo "[Stage: $STAGE] Starting run $task_id (CPUs: $start_cpu-$end_cpu)"

    # Use taskset for CPU affinity if available (append to log)
    if command -v taskset &> /dev/null; then
        taskset -c "${start_cpu}-${end_cpu}" \
            "${SCRIPT_DIR}/run_make.sh" \
            "$config_file" "$task_id" "$PLATFORM" "$DESIGN" "$STAGE" \
            >> "$log_file" 2>&1
    else
        "${SCRIPT_DIR}/run_make.sh" \
            "$config_file" "$task_id" "$PLATFORM" "$DESIGN" "$STAGE" \
            >> "$log_file" 2>&1
    fi
}

run_worker() {
    local worker_id=$1
    local start_cpu=$(( (worker_id-1) * CPUS_PER_RUN ))
    local end_cpu=$(( start_cpu + CPUS_PER_RUN - 1 ))
    local task_id
    local exit_code

    # Each worker reuses one CPU-affinity slot and processes a strided subset.
    for ((task_id=worker_id; task_id<=NUM_RUNS; task_id+=MAX_CONCURRENT_RUNS)); do
        if run_task "$task_id" "$start_cpu" "$end_cpu"; then
            printf '0\n' > "$STATUS_DIR/$task_id"
        else
            exit_code=$?
            printf '%s\n' "$exit_code" > "$STATUS_DIR/$task_id"
        fi
    done
}

for ((worker_id=1; worker_id<=MAX_CONCURRENT_RUNS; worker_id++)); do
    run_worker "$worker_id" &
    WORKER_PIDS+=($!)
done

echo "Launched $MAX_CONCURRENT_RUNS workers for $NUM_RUNS runs. Waiting for completion..."

# Wait for every worker so the stage barrier still covers all logical runs.
for pid in "${WORKER_PIDS[@]}"; do
    wait "$pid" || true
done

FAIL_COUNT=0
for ((run_id=1; run_id<=NUM_RUNS; run_id++)); do
    status_file="$STATUS_DIR/$run_id"
    if [[ -f "$status_file" ]]; then
        exit_code=$(<"$status_file")
    else
        exit_code=1
    fi

    if [[ "$exit_code" -eq 0 ]]; then
        echo "[Run $run_id] Completed successfully"
    else
        echo "[Run $run_id] FAILED (exit code: $exit_code)"
        FAILED_RUNS+=($run_id)
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done

echo ""
echo "Stage $STAGE complete: $((NUM_RUNS - FAIL_COUNT))/$NUM_RUNS succeeded"
if [[ ${#FAILED_RUNS[@]} -gt 0 ]]; then
    echo "Failed runs: ${FAILED_RUNS[*]}"
fi

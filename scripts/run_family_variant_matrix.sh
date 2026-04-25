#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

experiment_id="${1:-matrix_family_stratified_$(date +%Y%m%d_%H%M%S)}"
shift || true

exec python3 "${AGENT_ROOT}/scripts/run_variant_experiment_matrix.py" \
  --experiment-id "${experiment_id}" \
  --family-groups robust_base \
  --case-set default \
  --build-jobs 4 \
  --build-threads 10 \
  --eval-jobs 8 \
  --eval-threads 10 \
  --eval-timeout-sec 900 \
  "$@"

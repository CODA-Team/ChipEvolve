#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

experiment_id="${1:-matrix_family_stratified_$(date +%Y%m%d_%H%M%S)}"
shift || true

exec python3 "${AGENT_ROOT}/scripts/run_variant_experiment_matrix.py" \
  --experiment-id "${experiment_id}" \
  --family-groups ${DPL_EVOLVE_MATRIX_FAMILY_GROUPS:-robust_base} \
  --cases aes_nangate45 ibex_nangate45 jpeg_nangate45 ariane133_nangate45 bp_quad_nangate45 \
  --build-jobs "${DPL_EVOLVE_MATRIX_BUILD_JOBS:-4}" \
  --build-threads "${DPL_EVOLVE_MATRIX_BUILD_THREADS:-10}" \
  --eval-jobs "${DPL_EVOLVE_MATRIX_EVAL_JOBS:-8}" \
  --eval-threads "${DPL_EVOLVE_MATRIX_EVAL_THREADS:-10}" \
  --eval-timeout-sec "${DPL_EVOLVE_MATRIX_EVAL_TIMEOUT_SEC:-900}" \
  "$@"

#!/usr/bin/env bash
# Public entry point. Low-level flow commands run relative to flow/.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ $# -eq 0 || "${1:-}" == --help || "${1:-}" == -h ]]; then
    cat <<'EOF'
Usage: ./run.sh -p PLATFORM -d DESIGN [maindriver options]
Example:
  ./run.sh -p asap7 -d aes -o TNS_EVAL -i 25 -r 50 -s gwtw -A -P -F --seed 42 --cpus 250 -t 120m
Configuration: config/api.sh, optional config/env.local.sh
Detailed options: docs/RUNNING.md and docs/OPTIMIZER_GUIDE.md
EOF
    exit 0
fi
if [[ -d "$ROOT/.venv" ]]; then source "$ROOT/.venv/bin/activate"; fi
if [[ -f "$ROOT/config/env.local.sh" ]]; then source "$ROOT/config/env.local.sh"; fi
source "$ROOT/config/env.sh"
if [[ -f "$ROOT/config/api.sh" ]]; then source "$ROOT/config/api.sh"; fi
if [[ ! -d "$ROOT/flow/platforms" ]]; then
    echo 'Configure platform libraries first: python tools/setup_platforms.py --flow-root /path/to/ORFS/flow' >&2
    exit 1
fi
cd "$ROOT/flow"
exec bash ./maindriver.sh "$@"

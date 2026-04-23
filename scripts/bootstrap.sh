#!/usr/bin/env bash
set -euo pipefail

echo "[bootstrap] Recommended first sequence:"
echo "  1. Read evolve_agent/AGENTS.md"
echo "  2. Create a local baseline checkpoint:"
echo "     python3 evolve_agent/scripts/checkpoint.py create --checkpoint-id initial_pre_patch --title 'initial pre-patch baseline' --summary 'local baseline before the first bounded patch'"
echo "  3. Generate the current packet with kb_query.py"
echo "  4. Build and run one strict baseline line"

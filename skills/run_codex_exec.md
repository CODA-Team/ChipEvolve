# Skill: run_codex_exec

## Purpose
Run `codex exec` through the local control plane and record the invocation as a
local checkpoint operation.

## Canonical entrypoint
- `evolve_agent/scripts/run_codex_exec.py`

## What it records
- copied prompt text
- raw `codex exec --json` event stream
- stderr log
- last agent message
- token usage summary
- optional cost estimate if explicit price arguments are provided

## Important rule
Treat token counts as the primary ground truth.

Do not assume the CLI exposes account credits directly. If a cost estimate is
needed, pass explicit price-per-1M-token values at invocation time and treat
the result as an estimate, not account truth.

## Example

```bash
python3 evolve_agent/scripts/run_codex_exec.py \
  --operation-id codex_exec_smoke \
  --prompt-file evolve_agent/tasks/design_evolve/nangate45__gcd.md \
  --sandbox workspace-write
```

## Output location
- `evolve_agent/checkpoints/operations/<operation_id>/codex_usage_summary.json`

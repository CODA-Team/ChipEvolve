# Codex Prompt — nangate45/gcd

You are working in `OpenROAD-flow-scripts`.

Goal:
- perform one bounded code-evolve iteration for `./designs/nangate45/gcd/config.mk`
- assume basic place is already done by others
- reuse an existing `FLOW_VARIANT` that already contains `3_4_place_resized.odb`
- do **not** rerun place

Read first:
- `evolve_agent/AGENTS.md`
- `evolve_agent/baseline/canonical_lines.yaml`
- `evolve_agent/skills/patch_rules.md`
- `evolve_agent/problems/gcd_nangate45/problem.yaml`

Loop contract:
- the outer Python loop will create/restore checkpoints
- the outer Python loop will refresh the packet
- the outer Python loop will build and run the evaluator
- make one bounded patch only within the allowed patch surface, then stop

Preferred evaluator entrypoint:

```bash
python3 evolve_agent/adapters/science_codeevolve/evaluator.py \
  --problem evolve_agent/problems/gcd_nangate45/problem.yaml \
  --mode single \
  --line evolve_line \
  --flow-variant <REUSE_EXISTING_FLOW_VARIANT> \
  --run-tag <NEW_RUN_TAG> \
  --evolve-engine default \
  --threads 8 \
  --out evolve_agent/checkpoints/operations/<OPERATION_ID>/<EVAL_JSON>
```

Fallback:
- if no valid `3_4_place_resized.odb` exists for this design, stop and report that the required place snapshot is missing

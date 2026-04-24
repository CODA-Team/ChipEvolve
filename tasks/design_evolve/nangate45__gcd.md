# Codex Prompt — nangate45/gcd

You are working with a standalone `dpl_evolve_agent` control repo plus an
external ORFS workspace.

Goal:
- perform one bounded patch iteration for the `nangate45/gcd` legalizer case
- assume basic place is already done by others
- reuse an existing `FLOW_VARIANT` that already contains `3_4_place_resized.odb`
- do **not** rerun place

Read first:
- `$DPL_EVOLVE_AGENT_ROOT/AGENTS.md`
- `$DPL_EVOLVE_PACKET_DIR/current_run_packet.md`
- `$DPL_EVOLVE_AGENT_ROOT/skills/patch_rules.md`
- `$DPL_EVOLVE_AGENT_ROOT/problems/gcd_nangate45/problem.yaml`

Loop contract:
- the outer Python loop will create/restore checkpoints
- the outer Python loop will refresh the packet
- the outer Python loop will build and run the evaluator
- the outer loop owns `ORFS_ROOT`, `DPL_EVOLVE_AGENT_ROOT`,
  `DPL_EVOLVE_STATE_ROOT`, and any explicit `OPENROAD_BINARY`
- make one bounded patch only within the allowed patch surface, then stop
- do not inspect `flow/Makefile`, `flow/scripts/*`, or `flow/designs/nangate45/gcd/config.mk`
  unless the task explicitly expands beyond the target plane
- the reusable place snapshot has already been validated by the outer loop
- the baseline evaluator has already run before Codex is invoked
- do not open archive protocols, delta ledgers, or stage-context notes unless
  the packet is missing a required fact
- do not inspect git history or broad repo status unless the task explicitly
  expands into flow debugging
- start from `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.cpp`
  unless the packet explicitly names another file

Preferred evaluator entrypoint:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/evaluator.py" \
  --problem "$DPL_EVOLVE_AGENT_ROOT/problems/gcd_nangate45/problem.yaml" \
  --mode single \
  --line evolve_line \
  --flow-variant <REUSE_EXISTING_FLOW_VARIANT> \
  --run-tag <NEW_RUN_TAG> \
  --evolve-engine default \
  --threads 8 \
  --out "$DPL_EVOLVE_OPERATIONS_DIR/<OPERATION_ID>/<EVAL_JSON>"
```

Focus:
- trust the packet for track, patch surface, and hard gates
- inspect the target file you plan to patch, make one bounded change, then stop

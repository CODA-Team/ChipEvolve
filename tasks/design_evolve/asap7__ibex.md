# Codex Prompt — asap7/ibex

You are working in `OpenROAD-flow-scripts`.

Goal:
- perform one bounded code-evolve iteration for `./designs/asap7/ibex/config.mk`
- assume basic place is already done by others
- reuse an existing `FLOW_VARIANT` that already contains `3_4_place_resized.odb`
- do **not** rerun place

Read first:
- `evolve_agent/AGENTS.md`
- `evolve_agent/skills/patch_rules.md`
- `evolve_agent/tasks/archive/FIRST_BOUNDED_PATCH_PROTOCOL.md`
- `evolve_agent/problems/ibex_asap7/problem.yaml`

Required steps:
1. Create a local checkpoint before editing.
2. Refresh the packet:
   `python3 evolve_agent/adapters/science_codeevolve/kb_query.py --problem_dir evolve_agent/problems/ibex_asap7 --out_dir evolve_agent/knowledge/packets`
3. Discover the latest reusable `FLOW_VARIANT` under `flow/results/asap7/ibex/` that contains `3_4_place_resized.odb`.
4. Make one bounded patch only within the allowed patch surface.
5. Build with `./build_openroad.sh --local`.
6. Run one strict evolve line with a fresh run tag. Start from `--evolve-engine default`; switch to `negotiation` only if the patch explicitly targets the negotiation family.
7. Write evaluator output under `evolve_agent/checkpoints/operations/<operation_id>/`.
8. Report touched files, reused flow variant, run tag, metrics path, legality, HPWL delta, displacement, runtime, and keep/revise/restore decision.

Preferred evaluator entrypoint:

```bash
python3 evolve_agent/adapters/science_codeevolve/evaluator.py \
  --problem evolve_agent/problems/ibex_asap7/problem.yaml \
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

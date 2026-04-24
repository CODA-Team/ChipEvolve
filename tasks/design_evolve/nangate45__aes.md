# Codex Prompt - nangate45/aes

Use this prompt only for a loop-driven bounded patch turn.

The outer Python loop owns prepare, checkpoint restore, packet refresh, build,
evaluation, scoring, and accept/reject. Your job is only to make one small
source patch.

Read only:
- `$DPL_EVOLVE_PACKET_DIR/current_run_packet.md`
- `$DPL_EVOLVE_AGENT_ROOT/skills/patch_rules.md`
- `$DPL_EVOLVE_AGENT_ROOT/problems/aes_nangate45/problem.yaml`
- the one target source file named by the packet

Do:
1. Inspect the packet and the named target file.
2. Apply one bounded mechanism-specific patch under `tools/OpenROAD/src/dpl_evolve/`.
3. Stop after the patch and summarize the mechanism, expected metric effect, and rollback condition.

Do not:
- do not run build, evaluator, place, or checkpoint commands
- do not discover `FLOW_VARIANT`; the outer loop already selected it
- do not inspect `flow/Makefile`, `flow/scripts/*`, or design `config.mk`
- do not open archive protocols, delta ledgers, stage-context notes, design profiles, or git history
- do not use legacy in-ORFS control-plane paths; this is a standalone `DPL_EVOLVE_AGENT_ROOT` repo

Default starting file:
- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.cpp`

Hard gates:
- legality must remain clean
- `metrics.json` must exist after the outer evaluator runs
- runtime and displacement regressions need a clear compensating reason

# Teacher/Child Case Evolution Loop

The current DPL-Evolve direction is no longer "grow many historical families."
The stable entrypoint is `detailed_placement_evolve`, and the algorithmic
implementation inside `tools/OpenROAD/src/dpl_evolve` is intentionally
evolvable case by case.

## Roles

Teacher Agent:

- owns the case-level objective and evidence,
- compares against Diamond/openroad baselines,
- assigns distinct hypotheses to child workers,
- reads each child's result artifacts,
- reviews child code changes, diffs/patches, telemetry, logs, and metrics,
- explains why each implementation helped, failed, or merely shifted cost,
- promotes only one or two promising directions into the next round.

Child Agent:

- owns one bounded mechanism for one round,
- continues its own code lineage across iterations when Teacher keeps it alive,
- starts from concrete source references, not blank brainstorming,
- edits only the evolved DPL implementation surface,
- builds and evaluates its own candidate,
- reports touched files, mechanism, metrics path, telemetry, and rollback
  condition,
- does not edit evaluator, benchmark selection, or classic `dpl`.

## Multi-Iteration Loop

1. The orchestrator refreshes the canonical baseline suite for the case:
   `openroad_dpl_flow` and `evolve_default`.
2. Teacher reads the current packet, the baseline metrics table, and the
   explicit report/log/result paths for those baseline rows.
3. Teacher dispatches children with non-overlapping hypotheses:
   - Stage A relaxed/differential guidance,
   - Stage2 row/segment assignment quality,
   - Stage3 bounded HPWL/displacement polish,
   - large-case runtime guard/bypass,
   - ALM/BGD paper-fidelity improvements,
   - telemetry and stage selector.
4. Each child starts from:
   - the current `tools/OpenROAD/src/dpl_evolve/src` framework,
   - `family_variants/legalm_guidance`,
   - one relevant donor such as Diamond, NBLG, LEGALM, or DREAMPlace/Abacus,
   - Teacher's case-specific top-level framework guidance.
5. Each child implements one idea and runs the strict evaluator.
6. Teacher reads every child's `codex_last_message`, operation summary,
   reported metrics, changed source code, and relevant logs.
7. Teacher rejects failures and weak evidence, keeps promising directions, and
   writes concrete continuation guidance for the same student ids.
8. The next iteration sends those students back to their own lineage instead
   of restarting from unrelated ideas.
9. Repeat until the case beats the OpenROAD DPL flow anchor on strict HPWL
   while preserving legality, runtime, and displacement guards.

## Entry Script

Use:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case jpeg_nangate45 \
  --children 4 \
  --iterations 2 \
  --dry-run
```

Add `--launch` to actually call `codex exec` through `run_codex_exec.py`.

The script writes a round directory under:

```text
$DPL_EVOLVE_STATE_ROOT/teacher_rounds/<round_id>/
```

The round directory contains:

- `iter_XX/packet/current_run_packet.md`,
- `iter_XX/prompts/teacher_plan.md`,
- `iter_XX/prompts/student_XX_*.md`,
- `iter_XX/prompts/teacher_review.md`,
- `students/student_XX/lineage.json`,
- `manifest.json`,
- `README.md` with launch commands and baseline evidence.

## Promotion Rule

A child result is only useful if it provides:

- clean build,
- strict legal result,
- HPWL/runtime/displacement comparison against baseline,
- telemetry explaining which stage produced the effect,
- a rollback condition.

Fallback-to-default behavior is diagnostic, not success evidence.

# Skills

Repo-local operating notes for `dpl_evolve_agent`.

Read only the skill needed for the current action:

- `patch_rules.md`: bounded patch surfaces and forbidden reads.
- `build_openroad.md`: common-core plus variant-relink build.
- `evaluate_run.md`: guarded evaluator and result interpretation.
- `run_single_baseline.md`: manual one-line baseline/evolve runs.
- `run_baseline_suite.md`: manual suite runs.
- `run_codex_exec.md`: external `codex exec` logging wrapper.
- `teacher_peer_coaching.md`: Teacher-side peer-learning and feedback protocol
  for multi-student optimization rounds.

Default for loop-driven Codex turns:

- read `patch_rules.md`
- patch one target source file
- do not build or evaluate

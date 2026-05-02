# Skills

Repo-local operating notes for `dpl_evolve_agent`.

Read only the skill needed for the current action:

- `patch_rules.md`: bounded patch surfaces and forbidden reads.
- `build_openroad.md`: common-core plus variant-relink build.
- `evaluate_run.md`: guarded evaluator and result interpretation.
- `../knowledge/insights/workflow/metric_contract.md`: canonical HPWL and
  report interpretation contract.
- `run_single_baseline.md`: manual one-line baseline/evolve runs.
- `run_baseline_suite.md`: manual suite runs.
- `run_codex_exec.md`: external `codex exec` logging wrapper.
- `teacher_peer_coaching.md`: Teacher-side peer-learning and feedback protocol
  for multi-student optimization rounds.

Default for loop-driven Codex turns:

- read `patch_rules.md`
- implement one coherent mechanism on the assigned private `dpl_evolve` source
- touch legalization/detailed placement, improve placement, or their shared
  objective/handoff as directed by Teacher
- let the orchestrator-owned packet decide whether this worker should build
  and evaluate

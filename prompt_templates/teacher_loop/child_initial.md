# Child Worker $child_id: $student_id

Iteration: `$iteration_name`

Context file: `$context_path`

Peer learning packet: `$peer_learning_path`

## Exploration Seed

$strategy_brief

Seed = hypothesis, not boundary. Keep, combine, discard, or pivot.

## Generated Workspace Packet

Read for exact paths, prepare/build/evaluate commands, and artifact locations:

`$workspace_packet_path`

Mandatory gate: prepare, build, evaluate, non-empty diff, non-empty knowledge
card, exact artifacts.

## Teacher Insight

- Teacher plan: `$teacher_plan_last_message`
- your `### $student_id` insight is appended below

## Required Behavior

- Edit only private `dpl_evolve`; never edit evaluator, baseline Tcl, benchmark
  selection, root ORFS source, or classic `tools/OpenROAD/src/dpl`.
- Keep the public evolved flow callable:
  `detailed_placement_evolve -> improve_placement_evolve -> optimize_mirroring_evolve`.
- Implement one coherent case-specific flow change across all three commands.
  Constants, quotas, and thresholds can support the mechanism but cannot be the
  mechanism.
- You may change objective, stage order, legalization, assignment, repair,
  improve placement, mirroring, telemetry, commit logic, and data structures.
- Strict legality is mandatory.  Optimize HPWL first; explain runtime and
  displacement as tradeoffs.

## Mandatory Three-Part Implementation

Do not stop after one local change. A valid attempt has non-empty source edits
in all three areas, plus a final co-optimization pass:

- Legalization: change global guidance, row assignment, candidate scoring,
  Stage 3 refinement, repair handoff, or legalization objective.
- Improve placement: change detailed objective, candidate generator, manager,
  swap/reorder/vertical/orient pass, touched-net scoring, or commit policy.
- Mirror: change mirror/orientation scoring, acceptance, ordering, candidate
  filtering, or its interaction with detailed improve.
- Co-optimization: connect the three parts through a shared objective, touched
  net/cache data, displacement/reference snapshots, stage handoff, telemetry,
  or flow ordering decision.

Before editing, inspect the relevant current source and write down the intended
three-part mechanism in your own notes. After editing the three parts, revisit
the top-level flow once and make the stages work together; do not leave them as
three unrelated tweaks. If your final diff touches only one or two areas, treat
the attempt as incomplete.

## Mechanism Menu

Use the active case evidence: density, displacement tail, net structure, failed
stages, and baseline behavior.  Strong directions include early net/size-aware
row assignment, touched-net HPWL deltas, dirty-row legality, sparse snapshots,
cheap branch predictors, checkpointed endpoint search, isolated-state
parallelism, and flow-order changes across legalize/improve/mirror.

Avoid low-value work: pure retunes, blind branch proliferation, case-name
hardcoding, default-equivalent/no-op behavior, or local proxy-only wins.

## Implementation Standard

- Expect a substantial diff. Prefer changing several focused source files over
  hiding the whole idea in one flag or constant.
- High-performance C++: bounded candidates, cached row/net/branch state, no
  avoidable hot-loop O(n^2), no full-grid inner loops.
- Avoid excessive defensive programming.  Do not add broad safety wrappers,
  repeated full validation, or hot-loop guard clutter to mask uncontrolled
  logic.
- Make invalid moves unrepresentable or reject them before commit.
- Telemetry and knowledge card must state candidate cap, touched-data scope,
  cache lifetime, expected complexity, accepted moves, legality vetoes, and
  rejection reason.

## Final Response Required

Report: touched files, mechanism, build/eval status, metrics path, private
binary, diff path, knowledge card path, HPWL/runtime/displacement delta,
telemetry, algorithmic validity and complexity assessment. Explicitly state the
legalization change, improve-placement change, mirror change, and cross-stage
co-optimization.

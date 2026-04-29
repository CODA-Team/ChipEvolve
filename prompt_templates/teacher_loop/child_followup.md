# Student Follow-Up: $student_id

Iteration: `$iteration_name`

Context file: `$context_path`

Peer learning packet: `$peer_learning_path`

Use Teacher insight, change code, build, evaluate, report delta. You choose the implementation.

## Teacher Insight

- Teacher insight source: `$teacher_plan_last_message`
- your `### $student_id` insight is appended below

## Generated Workspace Packet

Read for exact paths, commands, run tag, and artifact locations:

`$workspace_packet_path`

Mandatory gate: prepare, build, evaluate, non-empty diff, non-empty knowledge
card, exact artifacts.

## Current Iteration

- case: `$case_id`
- flow_variant: `$flow_variant`
- threads: `$threads`
- run_tag: `$run_tag`

$elite_note

## Peer Results To Use, Not Re-Analyze

$peer_context

## Required Behavior

- Edit only private `dpl_evolve`; use the workspace packet for exact commands.
- Implement one coherent case-specific flow change across legalization, improve
  placement, and mirror. Constants or thresholds may support it, but cannot be
  the main contribution.
- You may change objective, flow order, scoring, legalization, repair, improve
  placement, mirroring, telemetry, commit logic, or data structures.
- Strict legality is mandatory; HPWL is the main target.
- Write a knowledge card explaining what future students should borrow or avoid.

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

Use Teacher insight and peer results to choose the mechanism, then execute it.
After editing the three parts, revisit the top-level flow once and make the
stages work together. If your final diff touches only one or two areas, treat
the attempt as incomplete.

## Mechanism Direction

Use Teacher insight and peer evidence, then make your own code decision.  If
borrowing a donor, change one important part: make it faster, earlier in the
flow, more net-aware, more transferable, or more scalable.

High-value tools: early net/size-aware assignment, touched-net HPWL deltas,
dirty-row legality, sparse snapshots, cheap predictors, checkpointed endpoint
search, isolated-state parallelism, and legalize/improve/mirror flow-order
changes.

Avoid weak repeats: pure retunes, blind branches, case-name hardcoding,
default-equivalent/no-op behavior, or local proxy-only wins.

## Implementation Standard

- Expect a substantial diff. Prefer changing several focused source files over
  hiding the whole idea in one flag or constant.
- High-performance C++: bounded candidates, cached row/net/branch state,
  deterministic tie-breaks, no avoidable hot-loop O(n^2).
- Prefer incremental touched metrics over full rescans.
- Avoid excessive defensive programming: no broad catch-all logic, repeated
  full validation, redundant safety layers, or hot-loop guard clutter.
- Telemetry and knowledge card must state candidate cap, touched-data scope,
  cache lifetime, expected complexity, accepted moves, legality vetoes, and
  why the candidate should scale or why it failed.

## Instructions

- read your `### $student_id` insight from the Teacher note appended below
- do not redo the global comparison
- inspect peer code only when it helps the concrete change you choose
- continue your private source lineage unless Teacher requested a pivot
- use the generated workspace packet for prepare/build/evaluate/diff
- final answer: touched files, mechanism, build/eval status, metrics path,
  HPWL/runtime/displacement delta, diff path, knowledge card path, next uncertainty
- explicitly state the legalization change, improve-placement change, mirror
  change, and cross-stage co-optimization

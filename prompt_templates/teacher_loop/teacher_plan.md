# Teacher Planning Task

Context file: `$context_path`

Read context. Set target. Write compact per-student insight.
No implementation. No shell commands. No exact private paths.
Borrow freely from Diamond, NBLG/negotiation, LEGALM, DREAMPlace/Abacus, and peer results.
First, read `Design Characteristics`; use it to tell students what this design
looks like before assigning directions.

## Student Exploration Seeds

$strategy_lines

## Policy

- Target strict legal HPWL. Runtime and displacement are tradeoffs to explain.
- Seeds are hypotheses, not boundaries. Students may change objective, flow
  order, legalization, repair, improve placement, mirroring, telemetry, commit
  logic, and data structures.
- Assign diverse, case-specific mechanisms. At least half the students should
  test major flow/objective/assignment/repair/mirroring changes.
- Treat tiny HPWL gains as donor evidence, not success.
- Require high-performance structure: bounded candidates, cached row/net data,
  safe parallelism, no hot-loop O(n^2), no repeated full validation as a crutch.
- Cross-pollinate useful peer mechanisms; do not freeze students with labels.

## Strategy Quality Bar

Push mechanisms that can change the frontier, not local polish: early net-aware
assignment, touched-net HPWL deltas, dirty-row legality, sparse snapshots, cheap
predictors, checkpointed endpoint search, isolated-state parallelism, and
legalize/improve/mirror flow-order changes.

For each student, name one primary mechanism, one structural efficiency
requirement, and the active-design property that should drive the choice.  If a
donor is strong but slow, ask for the faster algorithmic version, not another
blind branch.

## Output Required

Write only:

- one concise `Design read:` line covering density, population, baseline HPWL/runtime/displacement behavior, and likely bottleneck
- one concise global diagnosis
- `## Insight Packets`
- one `### student_XX` packet per student

Each packet:

- key insight
- useful peer/donor idea
- likely code area
- primary mechanism to implement
- efficiency requirement
- success target
- validity and complexity requirement
- knowledge to record

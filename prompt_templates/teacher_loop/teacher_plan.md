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

- target strict legal HPWL
- runtime is a tradeoff, not a veto
- prefer real algorithmic changes over constant retunes
- large moves are allowed with evidence and rollback
- seeds are hypotheses, not boundaries
- any student may change objective, flow order, net-aware/size-aware scoring,
  legalization, repair, polish, telemetry, or data structures
- keep student guidance compatible with high-performance C++ constraints:
  bounded candidates, cached row/net data, safe parallelism, no hot-loop O(n^2)
- cross-pollinate useful peer mechanisms
- do not freeze students with status labels

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
- success target
- risk/rollback guard

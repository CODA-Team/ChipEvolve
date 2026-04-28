# Cross-Case Transfer Matrix

## Evidence Type

This card summarizes a fixed-source transfer matrix: many evolved source
snapshots from one discovery line were evaluated unchanged across multiple
design families, utilization points, and technology settings.

Use this as transfer evidence, not as a case recipe.  Exact case ids and raw
paths belong in matrix artifacts, not in default agent context.

## Result Pattern

The strongest donor lineage beat most validation rows with about one percent
mean HPWL improvement.  Its mechanism family combined:

- global-spreading style anchoring,
- mild endpoint alternatives,
- transient legality checks,
- reference/snapshot displacement tracking,
- pruning of expensive or low-value branches.

The same donor was not universally safe.  It was expensive and failed on a
minority of validation rows.  A nearby lineage had slightly lower target-line
HPWL improvement but much lower displacement tail, making it a safer donor for
quality-sensitive follow-up.

## Boundary Condition

High-utilization rows remained the hardest boundary.  No evolved candidate
clearly beat the canonical flow there.  This suggests late polish and endpoint
branching are insufficient when whitespace is tight; future students should
move HPWL-aware decisions earlier into assignment, objective scoring, or flow
ordering.

## Mechanism Signals

Promising:

- transient legality: good aggregate signal when implemented cheaply,
- global-spreading anchoring: useful as a stabilizer but not sufficient alone,
- mild endpoint alternatives: useful guard, weak standalone strategy,
- exact touched-net HPWL tail polish: low-risk donor on some designs.

Weak or risky:

- fresh outlier repair without net-aware commit rules,
- overusing displacement snapshots as the main objective,
- row compaction without a strong branch selector,
- branch selection that improves only the discovery line and regresses transfer
  rows.

## Policy For Future Teacher Runs

Do not promote a mechanism only because it wins one discovery row.  Freeze the
same source snapshot and run the transfer matrix before treating it as
algorithm knowledge.

Teacher should pass students:

- the best aggregate donor source,
- the safer adjacent donor source,
- the simple donor that transfers well on large or row-rich designs,
- failed tags to avoid,
- whether the next round optimizes discovery-line maximum or transfer.

Students should still make larger algorithmic changes when stuck:

- alter legalize / improve / mirror flow order,
- move HPWL-aware scoring earlier,
- use net-aware or size-aware assignment,
- replace full scans with touched-net or dirty-row metrics,
- make branch selection cheap enough to test at scale.

Main lesson: fixed-source transfer separates robust mechanisms from single-case
tuning noise.

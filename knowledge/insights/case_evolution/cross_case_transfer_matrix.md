# Cross-Case Transfer Matrix

## Evidence Type

This card summarizes fixed-source transfer testing: evolved source states from
one discovery line are evaluated unchanged across multiple design families,
utilization points, and technology settings.

Use this as transfer evidence, not as a case recipe.  Exact case ids and raw
paths belong in matrix artifacts, not in default agent context.

Metric calibration: use this card as mechanism evidence only unless the source
matrix has been normalized under `workflow/metric_contract.md`.  Any older
table that relied on bbox HPWL proxy must be re-read through canonical
`metrics.json:hpwl` before promotion or publication.

Current ranking calibration: use
`case_evolution/score_based_case_strategy_routing.md` for the current
HPWL-plus-runtime `C_HR` ranking.  This card preserves the older transfer
mechanism lesson, not the active donor ordering.

## Result Pattern

The most useful HPWL-oriented donor lineages were not single heuristics.  Their
mechanism family combined:

- global-spreading style anchoring,
- mild endpoint alternatives,
- transient legality checks,
- reference displacement tracking,
- pruning of expensive or low-value branches.

The same donor may not be universally safe.  If it is expensive or fails on
some validation rows, compare it with nearby lineages that trade some HPWL for
lower displacement tail or better legality robustness.

## Boundary Condition

High-utilization rows are the hardest boundary.  If no evolved candidate clearly
beats the canonical flow there, late polish and endpoint branching are likely
insufficient when whitespace is tight; future students should move HPWL-aware
decisions earlier into assignment, objective scoring, or flow ordering.

## Mechanism Signals

Promising:

- transient legality: good aggregate signal when implemented cheaply,
- global-spreading anchoring: useful as a stabilizer but not sufficient alone,
- mild endpoint alternatives: useful guard, weak standalone strategy,
- exact touched-net HPWL tail polish: low-risk donor on some designs.

Weak or risky:

- fresh outlier repair without net-aware commit rules,
- overusing displacement references as the main objective,
- row compaction without a strong branch selector,
- branch selection that improves only the discovery line and regresses transfer
  rows.

## Policy For Future Teacher Runs

Do not promote a mechanism only because it wins one discovery row.  Freeze the
same source state and run the transfer matrix before treating it as
algorithm knowledge.

Teacher should pass students:

- the best aggregate donor source,
- the safer adjacent donor source,
- the simple donor that transfers well on large or row-rich designs,
- failed tags to avoid,
- whether the next round optimizes discovery-line maximum or transfer.

Students should still make larger algorithmic changes when stuck:

- alter legalize / improve flow order and source-level handoff,
- move HPWL-aware scoring earlier,
- use net-aware or size-aware assignment,
- replace full scans with touched-net or dirty-row metrics,
- make branch selection cheap enough to test at scale.

Main lesson: fixed-source transfer separates robust mechanisms from single-case
tuning noise.

# Fixed-Source Replay Transfer Evidence

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
HPWL-plus-runtime `G_HR` ranking.  This card preserves the older transfer
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

## Feature-Level Lessons From Transfer

Use transfer evidence as feature-level mechanism guidance.  A useful row should
be translated into a case feature, source mechanism, liveness signal, and
current-case validation target.

For actionable Teacher routing, use
`case_type_quality_mechanism_priority.md` first.  That card turns the transfer
lessons below into high-confidence case-type mechanism chains, start-kind
priors, source handles, and route playbooks.  This card explains why those
priors exist.

1. Dense/high-pressure standard-cell cases
   - Useful transfer signal: a legalizer may intentionally preserve a
     recoverable but not stage-optimal basin; the quality win comes from later
     exact DPO accepts.
   - Start/route prior: assign `framework` when stage evidence suggests a
     recoverable guidance/frontier basin; keep a Diamond-family guard only if
     the baseline basin is already close.
   - Try: recoverability-shaped legalizer producer, compact frontier handoff,
     exact source-edge or selected-segment consumer.
   - Source families: LEGALM guidance/closure, Student dispatch, Optdp exact
     DPO, and detailed global/reorder scoring.
   - Avoid: judging the mechanism by `HPWLlg` alone or adding more legalizer
     polish when final HPWL is erased downstream.

2. Row-local or edge-local residual cases
   - Useful transfer signal: small exact windows and source-edge candidates can
     transfer better than broad global replay.
   - Start/route prior: assign Diamond-family or local-closure starts when the
     legalizer is already stable; use guidance only if current evidence
     shows the local basin is wrong.
   - Try: selected row/segment exact reorder, local pair/swap transactions,
     affected-net scoring, accepted-gain early stop.
   - Source families: Diamond/local closure, detailed reorder, detailed global,
     and affected-net HPWL objective code.
   - Avoid: whole-design endpoint tails, random extra passes, or mirror-only
     protection without accepted exact moves.

3. Conflict-heavy or scarce-row cases
   - Useful transfer signal: primary legalizer role matters.  Negotiation or
     resource-allocation closure can be valuable only when it really executes
     and resolves conflicts.
   - Start/route prior: assign `default_negotiation` or
     `evolved_negotiation`; first prove the negotiation-primary route is live
     before tuning costs.
   - Try: negotiation-primary closure, resource reservation, compact conflict
     frontier consumed by DPO.
   - Source families: negotiation legalizer, negotiation repair, dispatch, DPO
     consumer, and algorithm-role liveness card.
   - Avoid: guidance producers that already make the placement legal before the
     conflict resolver runs, because that usually turns negotiation into a
     no-op donor.

4. Large row-rich designs
   - Useful transfer signal: quality donors can spend runtime productively when
     candidates are anchored on residual nodes, row windows, touched nets, or
     boundary-active regions.
   - Start/route prior: continue from the best current-run live legalizer seed,
     then add one deeper bounded DPO or residual-basin consumer.
   - Try: node-anchored row-window transactions, residual-basin objective
     repair, deterministic parallel scoring for independent candidates.
   - Source families: detailed manager, detailed global transaction logic, HPWL
     objective/journal code, and frontier-guided basin-consumer cards.
   - Avoid: full HPWL rescans and unbounded enumeration unless there is a cache,
     cap, and accepted-gain explanation.

5. Low-utilization or slack-rich designs
   - Useful transfer signal: simple local closure and source-edge exact moves
     often get most of the available HPWL without heavy global machinery.
   - Start/route prior: assign a stable Diamond/local start and a
     bounded exact local consumer before heavy basin escape.
   - Try: runtime-light local exact closure, source-edge top-K exact consumer,
     small rollback-safe reorder.
   - Source families: local closure, detailed reorder, source-edge candidate
     extraction, and affected-net scoring.
   - Avoid: heavy LSMC/restart families as the first route unless local exact
     consumers are live and plateaued.

6. Same-family plateau
   - Useful transfer signal: repeated threshold, counter, guard, or small
     source-edge variants rarely escape a plateau.
   - Start/route prior: preserve one current best continuation, then send other
     Students to different prepared starts and mechanism families matched to the
     observed failure mode.
   - Try: switch the reachable solution space: different producer policy,
     different DPO move family, or a new producer-consumer composition.
   - Source families: current-run peer refs and Student mechanism cards first;
     use broader cards only to design the next mechanism family.
   - Avoid: another route whose only change is constants, telemetry, ranking
     labels, or passive metadata.

## Policy For Future Teacher Runs

Do not promote a mechanism only because it wins one discovery row.  Freeze the
same source state and run the transfer matrix before treating it as
algorithm knowledge.

Teacher should pass students self-contained mechanism lessons:

- the mechanism class that transferred well;
- the case features where it helped or failed;
- the source files and functions in the current workspace where the mechanism
  should be rebuilt;
- liveness counters and stage metrics that prove the mechanism is actually
  active;
- failed tags or failure modes to avoid;
- whether the next round optimizes discovery-line maximum or transfer.

Students should still make larger algorithmic changes when stuck:

- alter legalize / improve flow order and source-level handoff,
- move HPWL-aware scoring earlier,
- use net-aware or size-aware assignment,
- replace full scans with touched-net or dirty-row metrics,
- make branch selection cheap enough to test at scale.

Main lesson: fixed-source transfer separates robust mechanisms from single-case
tuning noise.

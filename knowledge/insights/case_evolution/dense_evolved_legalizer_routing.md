# Dense Legalizer Routing Insight

## Evidence Type

Measured legalization-only evidence from the prior evolved-legalizer workspaces.
Use this as a stage-level routing prior for Teacher plans, not as a final-flow
rule.  For current full-flow promotion and case routing, read
`case_evolution/score_based_case_strategy_routing.md` first.

## Observation

On some high-utilization, standard-cell-dense placements, `evolved_legalm` was
the best measured legalization-stage donor among the three evolved legalizer
starts.  It reduced global-to-legal HPWL disturbance relative to the other
legalizer starts and to the clean local-greedy baseline.

The mechanism evidence in the LEGALM trace was not a tiny metadata change.  The
run activated high-pressure tail refinement and endpoint HPWL anchors:
frontier attempts, accepted interval/swap/chain moves, and exact HPWL gain
counters.

The same evolved legalizer ordering did not hold for all design archetypes, and
later full-flow evidence showed that even dense designs can prefer local closure
plus DPO or handoff repair.  Treat `evolved_legalm` as a dense-standard-cell
legalization prior, not as the default first parent and not as a final-flow
winner until strict final HPWL proves it on the active design.

Important calibration: this card is about legalization-stage behavior.  Later
full-flow rescoring showed that some high-utilization dense designs can regress
after LEGALM or NEGOTIATION even when a legal-stage metric looks better.  On
those features, `evolved_legalm` is a diagnostic or HPWL-stage donor unless
strict full-flow metrics prove it improves final HPWL. Prefer current
full-flow HPWL evidence when it names a different route such as
Diamond/local-DPO repair.

## Teacher Policy

Iteration 1 should intentionally diversify legalizer hypotheses:

- optionally assign one diagnostic dense-prior route from `evolved_legalm` when
  the case is high-utilization, standard-cell dense, or shows large legalization
  HPWL inflation from the global placement, unless current full-flow evidence
  already shows that LEGALM damages final HPWL for that case archetype,
- assign another route from `evolved_diamond` or Diamond-local behavior when
  the case has larger row/macro structure or needs local greedy closure,
- assign another route from `evolved_negotiation` when the case shows conflict
  or residual-overlap patterns that may need negotiation-style resolution,
- keep one route free for a hybrid or improve-placement-primary hypothesis when
  stage evidence says final HPWL is dominated by after-legal recovery.

From iteration 2 onward, Teacher should not keep all students on the same
initial line.  Use stage-wise attribution to decide one of three actions for
each student:

- continue the original direction if legal HPWL, after-improve recovery, and
  final strict HPWL move in the right direction,
- switch the student to a stronger route when its original direction loses at
  the stage it was meant to improve or improves a stage but damages final HPWL,
- hybridize routes when one legalizer gives a better legal state but another
  route or improve-placement mechanism recovers final HPWL better.

## Hybrid Pattern To Try

For dense cases, a plausible hybrid is:

- first run a bounded LEGALM/global-differential or high-pressure legalization
  phase to reduce the large global-to-legal HPWL disturbance,
- then run a bounded Diamond/local-greedy or negotiation-style residual phase
  on the cells/rows/nets left in bad local states,
- pass the frontier, touched nets, row pressure, or accepted-move tags into
  `improve_placement_evolve`,
- make `Optdp` consume that state with bounded local HPWL candidate scoring,
  not just a generic random tail.

This is an algorithmic stage sequence inside the evolved source, not a license
to rerun unchanged placement endpoints.  The Student should implement a clear
producer/consumer handoff between legalization and improve placement.

## Student Execution Expectation

Teacher packets should give a step-by-step chain, while still leaving the
Student room to plan the concrete patch:

1. Diagnose the case and current source around the assigned legalizer/improve
   hooks.
2. Implement the legalizer-stage change.
3. Implement the improve-placement consumer or companion change.
4. Build and evaluate canonical metrics.
5. Inspect stage-wise HPWL and runtime.
6. Revise once by either keeping the route, switching the weak stage to another
   legalizer family, or hybridizing two families.
7. Keep the best clean candidate and report the source-level evidence.

Do not encode benchmark names or local artifact paths in Teacher prompts from
this card.  Use it only as feature-level guidance: dense high-utilization
designs can have a strong LEGALM legal-stage donor, but final-flow promotion
still requires strict stage-wise evidence on the active design.

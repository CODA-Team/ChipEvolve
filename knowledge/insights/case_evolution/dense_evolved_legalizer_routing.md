# Dense Legalizer Routing Insight

## Evidence Type

Measured legalization-only evidence from the prior evolved-legalizer workspaces.
Use this as a routing prior for Teacher plans, not as a universal rule.

## Observation

On a high-utilization, standard-cell-dense image-compression snapshot,
`evolved_legalm` was the best measured legalizer among the three iter30 evolved
legalizer starts:

- `evolved_legalm`: legal HPWL delta about `+48.78%` from global HPWL,
  runtime about `13.0s`.
- `evolved_diamond`: legal HPWL delta about `+50.95%`, runtime about `13.8s`.
- `evolved_negotiation`: legal HPWL delta about `+51.73%`, runtime about
  `12.8s`.
- clean canonical Diamond-style legalizer was worse on this dense input, with
  legal HPWL delta about `+55.35%`.

The mechanism evidence in the LEGALM trace was not a tiny metadata change.  The
dense run activated high-pressure tail refinement and endpoint HPWL anchors:
thousands of frontier attempts, many accepted interval/swap/chain moves, and
large exact HPWL gain counters.

The same evolved legalizer ordering did not hold for all design archetypes.
For larger macro/row-rich snapshots, the evolved Diamond/local-greedy line was
often stronger.  Treat `evolved_legalm` as a dense-standard-cell prior, not as
the default for every case.

## Teacher Policy

Iteration 1 should intentionally diversify legalizer hypotheses:

- assign at least one dense-prior route from `evolved_legalm` when the case is
  high-utilization, standard-cell dense, or shows large legalization HPWL
  inflation from the global placement,
- assign another route from `evolved_diamond` or Diamond-local behavior when
  the case has larger row/macro structure or needs local greedy closure,
- assign another route from `evolved_negotiation` when the case shows conflict
  or residual-overlap patterns that may need negotiation-style resolution,
- keep one route free for a hybrid or improve-placement-primary hypothesis when
  stage evidence says final HPWL is dominated by after-legal recovery.

From iteration 2 onward, Teacher should not keep all students on the same
initial line.  Use stage-wise attribution to decide one of three actions for
each student:

- continue the original direction if both legal HPWL and after-improve recovery
  move in the right direction,
- switch the student to a stronger route when its original direction loses at
  the stage it was meant to improve,
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

## Evidence Pointers

- `dpl_evolve_agent_legalm/.dpl_evolve_state/legalization_workbench/evaluations/legalm_20iter_001_iter_30/summary.tsv`
- `dpl_evolve_agent_legalization_02/.dpl_evolve_state/legalization_workbench/evaluations/negotiation_20iter_001_iter_30/summary.tsv`
- `dpl_evolve_agent_legalization_03/.dpl_evolve_state/legalization_workbench/evaluations/diamond_20iter_001_iter_30/summary.tsv`
- `dpl_evolve_agent_legalm/agent_runs/legalm_20iter_001/traces/iter_30_trace.txt`

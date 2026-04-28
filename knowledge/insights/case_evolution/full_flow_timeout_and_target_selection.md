# Full-Flow Timeout And Target Selection

## Repository State

The active project line is the constrained `detailed_placement_evolve`
framework plus lightweight private variant relink.

The durable experiment boundary is:

- keep classic OpenROAD DPL and evaluator logic unchanged,
- edit only private `tools/OpenROAD/src/dpl_evolve` variant sources,
- relink private OpenROAD binaries,
- compare against `openroad_dpl_flow`,
- store runtime artifacts under ignored state/report/result directories.

## Large-Case Timeout Observation

On a very large benchmark, strict full-flow evaluation can exceed outer
timeouts even when legalization and placement checks have already succeeded.
The heavy part can be final metrics and downstream improvement work rather
than the legalizer itself.

Observed pattern:

- legalizer-stage runtime was comparable to the canonical flow,
- downstream improvement and mirroring dominated total elapsed time,
- a wrapper timeout that is acceptable for small and medium designs was too
  tight for full strict metrics on the large design.

Policy: use separate budgets for legalizer-only smoke, full placement flow, and
timing/power-style metrics.  Do not diagnose a legalizer as failed only because
the full metrics wrapper was too tight.

## Target Selection Policy

The main discovery case should be:

- large enough to expose runtime and quality tradeoffs,
- small enough to iterate quickly,
- sensitive to both HPWL and displacement tail,
- capable of running full strict metrics within the normal loop budget.

Before each Teacher/Student round:

- refresh `openroad_dpl_flow` and `evolve_default`,
- require strict legality and independent metrics,
- allow moderate runtime increase if HPWL meaningfully improves,
- report both legalizer-stage and final post-improve HPWL when available,
- preserve displacement tail and max displacement as guard metrics,
- require stage telemetry that explains the mechanism.

Do not treat "faster but same HPWL" as the main success criterion.  The goal is
to test whether aggressive case-specific algorithm changes beat the canonical
flow without changing the evaluator.

## Evolution Calibration

Medium-large discovery rounds showed that a candidate can beat the canonical
flow in one iteration and then regress in later iterations when students:

- continue weaker lineages,
- trust local proxy metrics too much,
- add more seeds or row coverage without improving final HPWL,
- optimize legalizer-stage numbers that are later erased by improve/mirror.

Policy: preserve the best-so-far strict artifact as an elite parent.  Let one
student continue it each iteration, while other students explore larger
changes.  Promote candidates only on final strict evaluator results, using
stage metrics for explanation rather than proof.

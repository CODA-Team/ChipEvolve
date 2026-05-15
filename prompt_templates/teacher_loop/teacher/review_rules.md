## Evidence Discipline

- Read the artifact packet once first; it already contains validity, metrics,
  artifact sizes, and exact paths.
- Prefer each student's `knowledge_card` for mechanism and lesson.
- Treat repeated artifact reads or post-clean reruns without a mechanism change
  as execution inefficiency and mention it briefly.
- Prefer Student-provided log/efficiency diagnosis when present. If it is
  missing, infer the minimum needed from `metrics.json`, DPL log counters, and
  artifact state; mark missing diagnosis as a reporting gap for that route.

## Validity Gate

- invalid if returncode failed, metrics missing, diff missing/empty, no agent
  message, or legality failed
- compare only canonical `metrics.json:hpwl`, runtime, avg/max displacement,
  stage-wise HPWL, and generated
  `G_HR = 100 * (HPWL_ref - HPWL_sol) / HPWL_ref - P(runtime_sol / runtime_ref), where P(r)=0 for r <= 1.10 and P(2.0)=1.0 percentage point`;
  ignore
  bbox/proxy wins
- use `G_HR` versus the OpenROAD DPL default-flow reference as the
  analysis value/balance metric only. Higher `G_HR` is better and the reference
  is 0, but it is not the elite-continuation objective. The research target and
  continuation key remain legal final HPWL under the hard runtime budget. Raw
  HPWL/stage deltas decide whether a higher-runtime candidate is still a useful
  donor or handoff repair route. Do not promote a faster but worse-final-HPWL
  candidate over a clean lower-HPWL candidate as the headline elite unless the
  lower-HPWL candidate violates legality, artifact gates, or the hard timeout
  budget.
- clean canonical HPWL 5% below the OpenROAD DPL default-flow reference is a credible research
  target, not a hard gate and not a ceiling
- sub-1% HPWL gains over `evolve_default` are donor evidence, not success
- repeated best HPWL, repeated donor code, tiny improvements, or repeated
  near-baseline runtime with sub-1% final movement are plateau/under-exploration
  signals

## Review Focus

- identify the real mechanism, not the claimed mechanism
- if the primary counter is zero, classify that mechanism as non-executed or
  negative evidence even when inherited code produced acceptable final metrics
- perform stage-wise attribution across legalization, improve placement,
  downstream final-pass contribution, runtime, and active trace counters
- compare each route against its selected LEGO-lite stage skills when present:
  source handles touched, expected transition, done criteria, and required log
  signals
- identify implementation/runtime failure modes separately from algorithmic
  failure: zero counters, timeout, stale source/binary/metrics, low accept
  rate, legality rejection, fallback domination, uncontrolled repeated work,
  untargeted scans, or missing cache/parallelism
- classify reusable evidence as `final donor`, `stage donor`, `active mechanism
  workbench`, `non-executed route`, `negative evidence`, or `quality-only but
  inefficient clue`
- convert `quality-only but inefficient clue` into a rewrite-for-efficiency
  route when HPWL or stage-wise evidence is strong: cache touched data, cap the
  frontier, parallelize independent scoring, or replace repeated endpoints with
  one bounded mechanism
- preserve a stage donor when it improves one stage but loses downstream;
  assign a handoff/consumer repair instead of discarding it
- preserve an active workbench for one focused repair when counters are
  nonzero, legality is clean, runtime is bounded, and either stage-local HPWL
  improved or the final erase is diagnosable
- classify runtime growth as useful controlled search, fixable implementation
  cost, or unsupported work. Do not over-reward routes that stay fast by
  avoiding the hard search.
- mark any runtime-heavy behavior as non-promotable only when it is uncontrolled
  or unsupported by counters. Repeated subpasses, broad scans, or randomized
  perturbations can be kept as donors when they are distilled into one scoped,
  measured source mechanism with handoff/frontier targeting and full-flow
  evidence.
- treat avg/max displacement as diagnostics, not hard success caps

## Next-Plan Requirements

- next plans must declare route emphasis: `legalizer-emphasis`,
  `DPO-emphasis`, or `co-optimization-emphasis`, with an ordered A/B/C plan
  chain. Emphasis is not exclusivity: students should improve both stages when
  there is a high-quality source mechanism, and otherwise explain the
  secondary stage as producer/consumer evidence rather than forcing no-value
  edits.
- if the next plan uses parameter tuning, require it to be source-internal:
  constants, thresholds, scoring weights, pass schedules, adaptive policies, or
  compact internal config structs in `dpl_evolve`. Reject Tcl/flow-script knob
  sweeps as black-box DSE, not white-box evolve.
- every packet needs one explicit `HPWL source mechanism`, why it can attack a
  materially larger remaining gap, and metric evidence that would prove or
  disprove it
- from iteration 2 onward, label each route `continue`, `switch`, or
  `hybridize`, justified by stage-wise HPWL, runtime, and counters
- `hybridize` means staged source-level mechanism composition inside the
  candidate implementation.  It must not be implemented as a case/scenario
  selector that jumps among complete legalizers, and it must not hide a
  fallback-to-default success path.
- for `continue` from an elite/final donor, use the pre-seeded/materialized
  elite source. Reserve `evolved_*` starts for explicit switch,
  hybridization, or stage-donor routes
- when dense/high-utilization standard-cell evidence shows large legalization
  HPWL inflation and `evolved_legalm` is stage-strong, preserve at least one
  LEGALM-derived or LEGALM-hybrid route unless its handoff is proven exhausted
- treat a global/differential route with useful legal-stage counters or HPWL as
  a stage donor even if pure greedy currently wins final HPWL; assign at least
  one detailed-repair or improve-placement-consumer repair before retiring that
  global path
- when a plateau is detected, at least half of the next packets should be
  source-discovery or stage-co-optimization routes, not narrow final-donor
  repairs
- when after-improve recovery is the failing stage, at least one route must
  repair improve placement directly and name the exact `Optdp`/`Detailed*`
  function/state plus the runtime tier it may consume
- when legal HPWL improves but final HPWL does not, assign a
  handoff/consumer repair; when final improves but legal HPWL is unchanged,
  ask how legalization can create a better frontier for that consumer
- hybrid plans must specify first legalizer family, residual/frontier handoff,
  second legalizer or repair family, and improve-placement consumer
- when feature-level insight suggests a strategy, translate it into one or two
  concrete source mechanisms and liveness counters.  Do not treat the feature
  card as a fixed route table.
- broader-search plans must state endpoint family size, candidate cap or
  touched-region bound, cache/reuse point, runtime tier, and whether OpenMP,
  thread-local caches, or deterministic reductions are appropriate
- next plans should include the log signals the Student must inspect after
  evaluation: expected active counters, accept/reject ratio, pass runtime,
  timeout/failure mode, and whether source/binary/metrics remain aligned after
  any revert or checkpoint restore
- next plans should name selected skill ids only when they clarify the route.
  Skill cards are reusable mechanism contracts, not a fixed menu that limits
  source-level judgment.
- if a route stalls, ask for a genuinely different hypothesis rather than
  another constant-only retune
- keep next packets concise: source mechanism, plan chain, exact function/state
  handles, source git expectations, and metric proof

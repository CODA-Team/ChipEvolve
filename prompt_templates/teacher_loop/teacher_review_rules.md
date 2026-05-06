## Evidence Discipline

- Read the artifact packet once first. It already contains validity, metrics,
  artifact sizes, and exact paths.
- Prefer each student's `knowledge_card` for mechanism/lesson.
- Treat repeated artifact reads or post-clean reruns without a mechanism change
  as execution inefficiency and mention it briefly.

## Validity Gate

- invalid if returncode failed, metrics missing, diff missing/empty, no agent
  message, or legality failed
- compare only canonical `metrics.json:hpwl`, runtime, avg/max displacement
- ignore bbox/proxy wins
- clean canonical HPWL 5% below the best clean canonical line is a
  credible research target, not a hard gate and not a ceiling
- keep the at-least-5% search belief unless canonical evidence shows the
  algorithmic space is exhausted
- sub-1% HPWL gains over `evolve_default` are donor evidence, not success
- repeated best HPWL, repeated donor code, or tiny improvements are plateau
  evidence.  Treat a plateau as a signal to search for a different large HPWL
  source, not as a reason to keep tuning the same local repair path.
- repeated near-baseline runtime with only sub-1% final HPWL movement is
  under-exploration evidence.  Preserve the best donor, but assign at least one
  next route to spend explore/aggressive runtime budget on a bounded larger
  mechanism.

## Review Focus

- identify the real mechanism, not the claimed mechanism
- if a student's primary mechanism counter is zero, classify that mechanism as
  non-executed or negative evidence even when inherited code produced an
  acceptable final metric
- compare students against baseline and peers
- perform stage-wise attribution: legalization, improve placement, downstream final-pass contribution, runtime, and which active stage caused the gain or loss
- report runtime tier: `fast` near baseline, `explore` moderate extra bounded
  search, or `aggressive` larger timeout-safe bounded search.  Decide whether
  runtime growth was useful search, fixable implementation cost, or wasted
  repetition.
- classify reusable evidence as `final donor`, `stage donor`, or `negative
  evidence`; do not let the final HPWL winner hide a weaker-final candidate
  whose earlier stage clearly improved
- classify donor efficiency separately from donor quality.  A large HPWL gain
  from excessive random/end-point replay is a quality-only signal, not an
  effective donor, until a bounded implementation proves similar gain.
- identify reusable donor code and why it works or fails
- identify whether the round discovered a new HPWL source or only retuned an
  existing donor.  A donor retune can be kept as a guardrail, but the next
  packets must not all be donor retunes.
- diagnose complexity: full rescans, endpoint explosion, repeated validation,
  unbounded loops, poor cache lifetime
- diagnose execution waste separately from algorithm value
- classify runtime growth as useful search, fixable implementation cost, or
  wasted repetition. Preserve high-HPWL-quality ideas when cost looks fixable,
  but require the next route to name what gets pruned, cached, bounded, or
  parallelized.
- Do not over-reward candidates that stay fast by avoiding the hard search.
  If the stage metrics show only local donor polishing, the next packet should
  deliberately allocate more runtime to a bounded search that attacks the
  remaining stage gap.
- judge runtime as part of the available budget: a route is acceptable when it
  has a bounded mechanism, useful stage-wise evidence, and finishes inside the
  student packet's ${student_runtime_multiplier}x DPL-flow timeout. This
  timeout applies to the OpenROAD legalize/improve/mirror flow, not to
  post-run metrics/evaluator collection.
- mark expensive incremental-only routes as non-promotable. Do not ask students
  to continue a path that only adds runtime for marginal HPWL; redirect them to
  a bounded structural mechanism.
- mark tiny safety/metadata/tie-break/veto changes as non-promotable when they
  do not expose a larger HPWL source.  Preserve the evidence, but redirect at
  least one student to a stronger hypothesis rather than another small variant.
- treat avg/max displacement as diagnostics, not hard success caps
- next plans must cover legalization/detailed placement and improve placement
- next plans may use Diamond/openroad_dpl_flow, openroad_dpl_negotiation, or
  evolve_default as the start-point evidence. If a Diamond-derived route wins or
  fails, review the exact reused behavior, the evolved source changes, and the
  stage where it helped or hurt.
- classify wins from repeated unchanged improve-placement runs, random tails,
  or endpoint stacking as runtime-buying evidence, not effective donors, until
  the idea is distilled into one bounded mechanism. Do not penalize a slower
  improve-placement-primary route when it uses the available timeout budget for
  a new controlled candidate/objective/acceptance mechanism with clear HPWL
  attribution.
- reward routes that embed improve-placement cost/candidates into legalization
  and show changed legalization HPWL, changed after-improve starting quality, or
  a clearly better legalization-to-improve handoff
- when after-improve recovery is the failing stage, require at least one next
  plan to repair improve placement directly. That plan's B stage must name the
  exact improve-placement state/function to change and the runtime budget it is
  allowed to consume.
- when legal HPWL is unchanged but final HPWL improved, require at least one
  next plan to ask how legalization can create a better frontier for that
  improve-placement mechanism.  When legal HPWL improved but final HPWL did
  not, require a handoff/consumer repair route instead of discarding the legal
  stage donor.
- require Teacher's next plans to analyze `Optdp` opportunities when final HPWL
  loss is dominated by poor after-improve recovery. The plan should distinguish
  real `Optdp` algorithm changes from script/telemetry-only changes.
- judge co-optimization explicitly: did legalization expose recoverable local
  choices, and did improve placement exploit them efficiently.
- next plans must include at least one `stage donor repair route` when any
  student improved a stage but lost the benefit in a later stage
- next plans must include an ordered `plan chain`: A legalization/detailed placement, B improve placement, and C optional coordination/selection when useful
- every next student packet must include one explicit `HPWL source mechanism`
- every next student packet must state why its `HPWL source mechanism` can
  attack a materially larger remaining HPWL gap than the current donor plateau
- next plans should keep students free to pivot across algorithm, objective,
  flow order, candidate generation, data structures, and hybrids when evidence
  shows the current direction cannot plausibly make material progress toward
  the 5% research target
- from iteration 2 onward, every next plan should label the route action:
  `continue`, `switch`, or `hybridize`. The label should be justified by
  stage-wise metrics: legalizer HPWL, improve-placement recovery, final HPWL,
  runtime, and active trace counters.
- for `continue` routes from an elite/final-donor lineage, tell the student to
  use the pre-seeded/materialized elite source. Do not name an `evolved_*`
  start branch as a clean-reset fallback; reserve `evolved_*` for explicit
  switch, hybridization, or stage-donor routes.
- when a dense/high-utilization standard-cell case shows large legalization
  HPWL inflation and `evolved_legalm` is stage-strong, preserve at least one
  LEGALM-derived or LEGALM-hybrid route unless metrics show its improve-stage
  handoff cannot be repaired.
- when a plateau is detected, at least half of the next packets should be
  source-discovery or stage-co-optimization routes rather than narrow repairs
  of the current final donor, unless there is clear evidence that the repair is
  itself the large HPWL source.
- for every next plan, explain the HPWL loss source being attacked, why it can
  be large enough to matter, and what metric evidence would prove or disprove
  the idea
- for hybrid next plans, specify the staged source-level flow: first legalizer
  family, residual/frontier handoff, second legalizer or repair family, and
  improve-placement consumer.
- for every next plan, include a bounded-search expectation: maximum endpoint
  family size, candidate cap or touched-region bound, and the evidence that
  should guide continued mechanism-driven revision versus stopping because the
  mechanism has already been tested
- for every next plan, include intended runtime tier and the specific extra
  work that tier buys.  Valid examples include broader capped row/segment
  windows, batched multi-cell transactions, exact affected-net scoring,
  parallel frontier scoring, and stronger legalizer/improve handoff state.
- keep next packets concise: one source mechanism, one plan chain, exact
  function/state handles, source git expectations, and metric proof. Avoid
  repeated rationale that makes the student prompt longer without changing the
  work.
- for every next plan that needs broader search, state whether parallel
  candidate evaluation, OpenMP, thread-local caches, or deterministic reductions
  are appropriate.  Encourage parallelism for independent scoring/probing loops
  when it improves useful search depth without changing the algorithm into an
  unbounded runtime trade.
- if a route stalls, ask for a genuinely different hypothesis, not another
  constant-only retune

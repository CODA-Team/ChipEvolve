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
- clean canonical HPWL 5% below the strongest clean canonical line is a
  credible research target, not a hard gate and not a ceiling
- keep the at-least-5% search belief unless canonical evidence shows the
  algorithmic space is exhausted
- sub-1% HPWL gains over `evolve_default` are donor evidence, not success
- repeated best HPWL, repeated donor code, or tiny improvements are plateau
  evidence.  Treat a plateau as a signal to search for a different large HPWL
  source, not as a reason to keep tuning the same local repair path.

## Review Focus

- identify the real mechanism, not the claimed mechanism
- compare students against baseline and peers
- perform stage-wise attribution: legalization, improve placement, final mirror
  contribution, runtime, and which stage caused the gain or loss
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
- judge runtime as acceptable or not for the case; slower-than-baseline is
  allowed only when HPWL gain or algorithmic evidence is substantial,
  complexity is controlled, and the route can finish inside the student
  packet's ${student_runtime_multiplier}x baseline timeout
- mark expensive incremental-only routes as non-promotable. Do not ask students
  to continue a path that only adds runtime for marginal HPWL; redirect them to
  a bounded structural mechanism.
- mark tiny safety/metadata/tie-break/veto changes as non-promotable when they
  do not expose a larger HPWL source.  Preserve the evidence, but redirect at
  least one student to a stronger hypothesis rather than another small variant.
- treat avg/max displacement as diagnostics, not hard success caps
- next plans must cover legalization, improve placement, and mirror/orientation
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
- require Teacher's next plans to analyze `Optdp` opportunities when final HPWL
  loss is dominated by poor after-improve recovery. The plan should distinguish
  real `Optdp` algorithm changes from script/telemetry-only changes.
- judge co-optimization explicitly: did legalization expose recoverable local
  choices, did improve placement exploit them efficiently, and did
  mirror/orientation preserve or improve the result.
- next plans must include at least one `stage donor repair route` when any
  student improved a stage but lost the benefit in a later stage
- next plans must include an ordered `plan chain`: A legalization, B improve
  placement, C mirror/orientation, and D optional coordination/selection when
  useful
- every next student packet must include one explicit `HPWL source mechanism`
- every next student packet must include a `breakthrough hypothesis`: why this
  route could attack a materially larger remaining HPWL gap than the current
  donor plateau
- next plans should keep students free to pivot across algorithm, objective,
  flow order, candidate generation, data structures, and hybrids when evidence
  shows the current direction cannot plausibly make material progress toward
  the 5% research target
- when a plateau is detected, at least half of the next packets should be
  source-discovery or stage-co-optimization routes rather than narrow repairs
  of the current final donor, unless there is clear evidence that the repair is
  itself the large HPWL source.
- for every next plan, explain the large HPWL opportunity: what HPWL loss source the
  student should attack, why it can be large enough to matter, and what metric
  evidence would prove or disprove the idea
- for every next plan, include a runtime-control expectation: maximum endpoint
  family size, candidate cap or touched-region bound, and when to stop rerunning
  because the mechanism has already been tested
- for every next plan that needs broader search, state whether parallel
  candidate evaluation, OpenMP, thread-local caches, or deterministic reductions
  are appropriate.  Encourage parallelism for independent scoring/probing loops
  when it improves useful search depth without changing the algorithm into an
  unbounded runtime trade.
- if a route stalls, ask for a genuinely different hypothesis, not another
  constant-only retune

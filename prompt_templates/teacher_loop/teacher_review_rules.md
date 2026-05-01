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
- clean canonical HPWL 5% below `openroad_dpl_flow` is a credible research
  target, not a hard gate and not a ceiling
- keep the at-least-5% search belief unless canonical evidence shows the
  algorithmic space is exhausted
- sub-1% HPWL gains over `evolve_default` are donor evidence, not success

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
- treat avg/max displacement as diagnostics, not hard success caps
- next plans must cover legalization, improve placement, and mirror/orientation
- next plans must not use Diamond, a Diamond-equivalent selector, or a plain
  Diamond anchor as the initial legalizer; keep Diamond only as the comparison
  baseline or optional reference check
- classify Diamond-copy, Diamond-wrapper, or Diamond-as-real-producer routes as
  negative evidence even if downstream improve placement makes the final HPWL
  look better
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
- next plans should keep students free to pivot across algorithm, objective,
  flow order, candidate generation, data structures, and hybrids when evidence
  shows the current direction cannot plausibly make material progress toward
  the 5% research target
- for every next plan, explain the large HPWL opportunity: what HPWL loss source the
  student should attack, why it can be large enough to matter, and what metric
  evidence would prove or disprove the idea
- for every next plan, include a runtime-control expectation: maximum endpoint
  family size, candidate cap or touched-region bound, and when to stop rerunning
  because the mechanism has already been tested
- if a route stalls, ask for a genuinely different hypothesis, not another
  constant-only retune

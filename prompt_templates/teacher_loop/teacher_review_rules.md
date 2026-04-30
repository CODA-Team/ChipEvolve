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
- final target is clean canonical HPWL at least 5% below `openroad_dpl_flow`
- keep the 5% target as the research assumption unless canonical evidence shows
  the algorithmic space is exhausted
- sub-1% HPWL gains over `evolve_default` are donor evidence, not success

## Review Focus

- identify the real mechanism, not the claimed mechanism
- compare students against baseline and peers
- identify reusable donor code and why it works or fails
- diagnose complexity: full rescans, endpoint explosion, repeated validation,
  unbounded loops, poor cache lifetime
- diagnose execution waste separately from algorithm value
- judge runtime as acceptable or not for the case; slower-than-baseline is
  allowed when HPWL gain or algorithmic evidence is substantial and complexity
  is controlled
- treat avg/max displacement as diagnostics, not hard success caps
- next plans must cover legalization, improve placement, and mirror/orientation
- next plans must include an ordered `plan chain`: A legalization, B improve
  placement, C mirror/orientation, and D optional coordination/selection when
  useful
- every next student packet must include one explicit `HPWL source mechanism`
- next plans should keep students free to pivot across algorithm, objective,
  flow order, candidate generation, data structures, and hybrids when evidence
  shows the current direction cannot plausibly approach the 5% goal
- for every next plan, explain the 5% opportunity: what HPWL loss source the
  student should attack, why it can be large enough to matter, and what metric
  evidence would prove or disprove the idea
- if a route stalls, ask for a genuinely different hypothesis, not another
  constant-only retune

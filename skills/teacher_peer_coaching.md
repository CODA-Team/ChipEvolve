# Teacher Peer Coaching

Use this skill when acting as the Teacher in a Teacher/Student optimization
round.  The goal is not to motivate students with pressure.  The goal is to
give each student enough evidence, peer lessons, autonomy, and mechanism
direction to make a strong source-level move.

## Teacher Role

- Synthesize evidence; do not re-run the whole investigation inside each
  student prompt.
- Teach through concise, case-specific insight packets.
- Preserve rigor: ask for build/eval evidence, strict legality, bounded
  complexity, and clear failure reports.
- Preserve autonomy: give mechanism direction and constraints, not line-by-line
  code commands.
- Preserve initiative: make students responsible for finding a stronger route
  when source evidence contradicts the initial plan.

## Before Assigning Students

Read:

- design characteristics,
- baseline table,
- previous round scoreboard,
- peer learning packet,
- review artifact packet when available,
- strongest and weakest implementation diffs when they explain behavior.

Then identify:

- one dominant case bottleneck,
- one or two mechanisms that worked,
- one or two mechanisms that failed and why,
- whether the round needs local refinement, a stage-level mechanism, optional
  stage coordination, or a full direction change.

If recent attempts repeat the same weak idea, switch perspective instead of
asking for another retune.  Name the failed assumption and assign a different
algorithmic route.

## Per-Student Packet Contract

Each student packet should include only:

- current diagnosis,
- peer or donor mechanism to borrow or avoid,
- one concrete legalization/detailed-placement direction,
- one concrete improve-placement direction,
- optional coordination/selection direction only when it has a concrete reason,
- expected complexity boundary,
- success metric,
- what knowledge card should record.

Use autonomy-supportive wording: Teacher gives insight, not a full design.
Students should trust their source-level judgment, verify with canonical
metrics, and pivot when evidence says the assigned route is weak.

Do not include shell commands, long paths, fear/pressure language, or broad
algorithm essays.

## Failure Response

If a student fails or produces a weak/no-op diff:

- First failure: point to the missing evidence or mechanism gap.
- Repeated same-direction failure: force a different mechanism class, not a
  parameter retune.
- Runtime failure: ask for cached/incremental/parallel structure, not smaller
  ambition.
- Legality failure: ask for a cleaner representation or commit path.
- Tiny HPWL win: preserve as donor evidence, but do not call it success unless
  it suggests a mechanism that can scale.
- Claimed completion without canonical metrics: require evidence, not prose.
- Repeated weak build/eval cycles: ask the student to stop, inspect the real
  failure signal, and change the algorithmic hypothesis.

## Peer Learning

When one student is better:

- tell other students what changed and what metric moved,
- tell them where the donor may be inefficient or brittle,
- ask them to borrow the mechanism, not copy the exact code blindly,
- require one meaningful mutation: earlier flow placement, better objective,
  cheaper data structure, stronger legality commit, or better transferability.

When no student is better:

- do not repeat the same plan,
- name the shared failed assumption,
- assign distinct alternative hypotheses.

## Anti-Patterns

- Do not create fear, competition pressure, or punishment language.
- Do not ask students to redo Teacher's global comparison.
- Do not reward no-op/default-equivalent diffs.
- Do not let every student work on the same small retune.
- Do not bury the useful action under long philosophical or explanatory prose.

## NoPUA Operating Style

Use the useful part of NoPUA-style coaching: trust, evidence, autonomy, and
initiative.  The student should hear: you can solve this by reading the source,
trying a real mechanism, verifying it, and changing direction when the evidence
demands it.  Do not use threats, shame, or artificial competition.

When a route stalls:

- switch perspective instead of repeating the same parameter search,
- read the original failure signal and relevant source,
- form a different hypothesis with a clear validation criterion,
- implement the smallest strong mechanism that can prove or disprove it,
- verify with canonical metrics and record the causal lesson.

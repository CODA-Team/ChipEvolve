# Teacher Peer Coaching

Use this skill when acting as the Teacher in a Teacher/Student optimization
round.  The goal is not to motivate students with pressure.  The goal is to
make each student receive the smallest useful packet of evidence, peer lessons,
and next mechanism direction.

## Teacher Role

- Synthesize evidence; do not re-run the whole investigation inside each
  student prompt.
- Teach through concise, case-specific insight packets.
- Preserve rigor: ask for build/eval evidence, strict legality, bounded
  complexity, and clear failure reports.
- Preserve autonomy: give mechanism direction and constraints, not line-by-line
  code commands.

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
- whether the round needs a local refinement, a cross-stage mechanism, or a
  full direction change.

## Per-Student Packet Contract

Each student packet should include only:

- current diagnosis,
- peer or donor mechanism to borrow or avoid,
- one concrete legalization direction,
- one concrete improve-placement direction,
- one concrete mirror/orientation direction,
- one cross-stage co-optimization direction,
- expected complexity boundary,
- success metric,
- what knowledge card should record.

Do not include shell commands, long paths, generic motivational text, or broad
algorithm essays.

## Failure Response

If a student fails or produces a weak/no-op diff:

- First failure: point to the missing evidence or mechanism gap.
- Repeated same-direction failure: force a different mechanism class, not a
  parameter retune.
- Runtime failure: ask for cached/incremental/parallel structure, not smaller
  ambition.
- Legality failure: ask for a cleaner representation or commit path, not broad
  defensive wrappers.
- Tiny HPWL win: preserve as donor evidence, but do not call it success unless
  it suggests a mechanism that can scale.

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
- Do not accept excessive defensive programming as rigor.
- Do not reward no-op/default-equivalent diffs.
- Do not let every student work on the same small retune.
- Do not bury the useful action under long philosophical or explanatory prose.

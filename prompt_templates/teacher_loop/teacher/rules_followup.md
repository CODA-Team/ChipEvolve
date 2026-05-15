# Teacher Follow-Up Rules

Use the prior session context as memory; do not restate global policy unless it
changes the next decision. Read only the current iteration context, peer packet,
and review packet fields needed for routing.

- Objective: legal final `metrics.json:hpwl` is the elite/promotion target.
  `G_HR` is analysis-only for runtime value; do not prefer faster worse-HPWL
  candidates unless lower-HPWL candidates fail legality/artifact/timeout gates.
- Runtime is a spendable search resource inside the hard budget, not a value to
  minimize by itself. If candidates are baseline-fast but HPWL-poor, assign a
  stronger bounded mechanism that intentionally spends runtime for HPWL.
- Route from stage-wise evidence: identify the current largest HPWL source and
  assign one primary mechanism hypothesis per Student with a minimal first-patch
  landing zone. Usually give 1-3 primary handles and at most 2 support
  handles; allow direct supporting edits across producer/consumer stages only
  when they are necessary for that hypothesis.
- Encourage coherent mechanism-level source rewrites when justified by Teacher
  evidence and source diagnosis; the constraint is bounded/reviewable/measured,
  not small.
- Avoid repeated micro-optimization loops. If a mechanism is live, correctly
  implemented, and still has extremely small full-flow HPWL movement after one
  meaningful repair, mark it `validated-low-ROI`, require `source_trials.jsonl`
  evidence from the trial helper, and assign a different HPWL source.
- If a rejected mechanism is implementation-bug or handoff-repairable rather
  than method-low-ROI, assign a repair trial from its ref with
  `25_trial_source.sh begin --from-ref <ref>`.
- Keep one best donor as regression guard, but do not make every route a donor
  polish. Plateau/tiny-gain rounds need `mechanism-redesign`, stage
  co-optimization, or a different legalizer/DPO/handoff hypothesis.
- Prepared starts are branch-only: `framework`, `diamond`, `evolved_diamond`,
  `evolved_legalm`, `evolved_negotiation`. Do not ask Students to manually
  apply release/start patch files.
- Limit selected mechanism skills: normally one primary mechanism skill, one
  auxiliary handoff/objective skill, and one optional diagnosis skill.
- Keep packets non-accumulative: one HPWL source, concise A/B/C plan, first-
  patch handles, minimal support handles, runtime tier, liveness counters,
  low-ROI stop rule, and metric proof.
  A/B/C may include preservation or diagnosis; do not require cosmetic edits.
  Replace stale guidance instead of appending history.

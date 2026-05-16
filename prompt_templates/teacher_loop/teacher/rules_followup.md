# Teacher Follow-Up Rules

Use the prior session context as memory; do not restate global policy unless it
changes the next decision. Read only the current iteration context, peer packet,
and review packet fields needed for routing.

- Role: act as the case-specific research lead and reviewer. Reuse prior
  knowledge-map decisions, but challenge weak mechanisms, distinguish
  implementation failure from method failure, and pivot to a new mechanism
  family when evidence shows weak gain, over-cost, or plateau.

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
- Use the first-round global route map as memory. Follow-up should read less
  and decide faster, but it must not forget routes that were never tested. If
  the best family stalls, reopen one broader algorithm card and assign a
  new-family route.
- Next-round direction must combine current metrics, Student knowledge-card
  reasoning, and one relevant knowledge/algorithm handle when the route changes
  family or claims a specific mechanism insight.
- Label every packet with `route type` and `route action`. If the previous
  useful results are same-family or tiny-gain, allow at most one `continue`
  guard/repair route; the other routes should `switch`, `hybridize`, or
  `mechanism-redesign` with a different producer/consumer mechanism.
- Route emphasis is not stage exclusion. In each follow-up round, preserve
  explicit coverage of legalizer-output quality, DPO-consumer strength, and
  handoff/co-optimization. A Student can prioritize one surface, but the packet
  should still say how the other two are changed, consumed, or deliberately
  held as guards. Avoid assigning a whole roster that only chases one DPO
  family or one legalizer family.
- Each non-guard route must say why it can beat a small donor by attacking a
  larger HPWL source. Same-family follow-up is valid only when it changes the
  mechanism class, not just thresholds, tie-breaks, counters, or local polish.
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
  polish. Tiny-gain, over-cost, or plateau rounds need `mechanism-redesign`,
  stage co-optimization, or a different legalizer/DPO/handoff hypothesis.
- Keep donor scope explicit: `general donor` means guard/reusable kernel;
  `feature-matched donor` means selected for this case's physical/stage
  features. Follow-up decisions should optimize this specific case first and
  record transferability as secondary evidence.
- Weak-gain / over-cost escalation is a review judgment, not a hard field. If
  current-run candidates are legal but tiny-gain, same-family, or too heavy for
  the HPWL gained, keep at most one guard route and assign at least one
  aggressive within-run route: switch mechanism family, redesign the
  producer/consumer pair, or continue from a current-run kept/rejected ref with
  `25_trial_source.sh begin --from-ref <ref>`.
- If assigning a branch/ref switch, name the source ref and new trial label, and
  require trial-helper branch preservation. Do not import cross-experiment
  donors or historical results as implementation starts.
- Prepared starts are branch-only: `framework`, `diamond`, `evolved_diamond`,
  `evolved_legalm`, `evolved_negotiation`. Do not ask Students to manually
  apply release/start patch files.
- Limit selected mechanism skills: normally one primary mechanism skill, one
  auxiliary handoff/objective skill, and one optional diagnosis skill.
- Keep packets non-accumulative: one HPWL source, concise A/B/C plan, first-
  patch handles, minimal support handles, runtime tier, liveness counters,
  low-ROI stop rule, and metric proof.
  A/B/C should cover legalization, DPO, and handoff behavior. Preservation or
  diagnosis is acceptable for guard/repair routes, but ordinary optimization
  routes should attempt a concrete producer-consumer connection rather than
  cosmetic edits.
  Replace stale guidance instead of appending history.

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
- Runtime is a hard budget and secondary value check, not a direction by
  itself. Assign heavier work only when the route names a missing HPWL source
  and changes a real mechanism with a cost-control path.
- Route from stage-wise evidence: identify the current largest HPWL source and
  assign one primary mechanism hypothesis per Student with a minimal first-patch
  landing zone. Usually give 1-3 primary handles and at most 2 support
  handles; allow direct supporting edits across producer/consumer stages only
  when they are necessary for that hypothesis.
- Use the first-round route map as memory. Follow-up should read less and
  decide faster, but it must not forget routes that were never tested. If the
  best family stalls, name the observed failure mode and assign a new-family
  route; open a broader algorithm card only when it provides a concrete
  mechanism for that failure mode.
- Before routing, restate the dominant HPWL source in one phrase: legalizer
  producer quality, DPO consumer strength, handoff/frontier loss, final
  mirror interaction, or composition. This source should drive the roster more
  than generic runtime headroom.
- Next-round direction must combine current metrics, Student knowledge-card
  reasoning, and targeted knowledge only when it clarifies the route change or
  mechanism insight. Current evidence wins over a knowledge card.
- Label every packet with `route type` and `route action`. If the previous
  useful results are same-family or tiny-gain, allow at most one `continue`
  guard/repair route; the other routes should `switch`, `hybridize`, or
  `mechanism-redesign` with a different producer/consumer mechanism.
- Route emphasis is not stage exclusion. In each follow-up round, preserve
  compatibility coverage of legalizer-output quality, DPO-consumer strength,
  and handoff/co-optimization. A Student can prioritize one surface; the packet
  should say how adjacent stages will consume, preserve, or validate that
  mechanism, but should not force cosmetic edits in every stage. Avoid assigning
  a whole roster that only chases one DPO family or one legalizer family.
- If the current winners are DPO/mirror-heavy, runtime-heavy, or tiny-gain,
  route at most one Student to continue that consumer family. Use the other
  slots for different HPWL sources: legalizer producer repair, placement
  shaping that preserves downstream recoverability, compact native handoff, or
  a genuinely new bounded DPO move family.
- Each non-guard route must say why it can beat a small donor by attacking a
  larger HPWL source. Same-family follow-up is valid only when it changes the
  mechanism class, not just thresholds, tie-breaks, counters, or local polish.
- Encourage coherent mechanism-level source rewrites when justified by Teacher
  evidence and source diagnosis; the constraint is bounded/reviewable/measured,
  not small.
- Require each non-guard Student to diagnose the current source before coding
  and to design an efficient implementation path for the chosen mechanism:
  capped candidate generation, cached/touched-net scoring, compact frontier
  state, or parallel independent probes where useful. Do not assign a route
  whose plan is only "try more DPO work" without a new HPWL source hypothesis.
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
- Keep packets non-accumulative: one HPWL source, concise dominant-mechanism
  plan, first-patch handles, minimal support handles, runtime tier, liveness counters,
  low-ROI stop rule, and metric proof.
  Adjacent-stage notes should prove compatibility or handoff needs, not force
  equal edits across legalization, DPO, and handoff.
  Replace stale guidance instead of appending history.

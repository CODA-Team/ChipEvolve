# Teacher Rules

## Objective And Evidence

- Promote only legal candidates by final `metrics.json:hpwl`; ignore proxy HPWL.
- `G_HR = 100 * (HPWL_ref - HPWL_sol) / HPWL_ref - P(runtime_sol / runtime_ref), where P(r)=0 for r <= 1.10 and P(2.0)=1.0 percentage point` is analysis-only. Use it to explain whether runtime is worth the HPWL gain, not as the elite selector.
- Runtime is a `${student_runtime_multiplier}x` hard budget and a search resource for the evaluated DPL flow. Teacher should expect Students to spend some of that budget on stronger bounded HPWL exploration when the mechanism is plausible. A faster but worse-final-HPWL candidate is runtime/control evidence unless the lower-HPWL candidate fails legality, artifacts, or timeout.
- Always inspect stage-wise evidence before routing: `HPWLg`, legalization delta, improve-placement delta, final HPWL, legality, displacement, runtime, logs, and liveness counters.
- Compare `openroad_dpl_flow`, `openroad_dpl_negotiation`, and `evolve_default` as evidence. The OpenROAD DPL default-flow row is the value reference.
- First-round Teacher planning should spend real effort on a global mechanism
  scan. Query knowledge broadly enough to identify several plausible legalizer,
  DPO, and handoff families, then turn them into a case-specific route map.
  Follow-up planning should read less and exploit the first-round map unless
  poor-basin/plateau evidence requires a new-family search.

## Mechanism Search Policy

- Give each Student one primary HPWL-source hypothesis with a minimal first-patch landing zone, a falsifiable metric outcome, runtime tier, and liveness counters. The first patch landing zone should usually be 1-3 primary handles; supporting producer/consumer edits may name at most 2 extra support handles when they are necessary for the hypothesis.
- Route Students toward an early first patch/build/eval loop. Do not assign broad "read more first" work when the current HPWL source and source handles are already clear enough to test a mechanism.
- Mechanism-level source rewrites are allowed and expected when evidence supports them. The constraint is coherent, bounded, reviewable, measurable, and full-flow validated; it is not "small edit only".
- First-round route diversity matters. Spread Students across distinct
  mechanism families such as legalizer composition, DPO kernel redesign, handoff
  consumer, and aggressive bounded basin search when those are plausible for
  the case. Later rounds may concentrate on the best family once evidence
  supports it.
- Every Student packet must label `route type` and `route action`. Use
  `continue` for at most one guard/repair route unless all other evidence is
  broken; otherwise use `switch`, `hybridize`, or `mechanism-redesign` when the
  last useful results are same-family or tiny-gain.
- Each non-guard route must state why it can beat a small donor: the larger
  HPWL source it attacks, the mechanism class it changes, and the expected
  stage-wise movement. A same-family route must change the mechanism class, not
  only constants, tie-breaks, or telemetry.
- Route emphasis can be `legalizer-emphasis`, `DPO-emphasis`, or `co-optimization-emphasis`. This is a priority label, not permission to ignore the other stage. If a stage is not patched, require a concrete diagnosis of how it preserves, consumes, or erases the gain.
- Use a short A/B/C chain: A legalization/detailed-placement, B improve-placement/DPO, C handoff/co-optimization. A/B/C can be real source changes or explicit preservation/diagnosis; do not force cosmetic edits just to fill a stage.
- If a verified live mechanism gives only extremely small full-flow HPWL movement after a meaningful repair attempt, mark it `validated-low-ROI`, require `source_trials.jsonl` evidence from the trial helper, and assign a different HPWL source. Do not keep assigning tie-break, threshold, or donor-polish variants.
- If stage-local gain is erased downstream, preserve it as a stage donor and route the next work to handoff or consumer repair.
- If review finds a rejected mechanism is implementation-bug or handoff-repairable rather than method-low-ROI, explicitly assign a repair trial from its ref using `25_trial_source.sh begin --from-ref <ref>`.
- Hybrid means staged mechanisms inside one source implementation, such as global/differential guidance, native legal closure, local HPWL repair, and a DPO consumer. Do not implement hybrid as a case-level selector among complete legalizers.
- Poor-basin rule: if the start seed or best clean candidate remains worse than the OpenROAD DPL default-flow HPWL after a meaningful attempt, preserve at most one guard/polish route and assign at least one Student to a `mechanism-redesign` or different legalizer/DPO composition. That route should come from a broader skill query plus one algorithm/pseudocode card outside the current donor family, not another threshold/tie-break retune.

## Starts, Knowledge, And Skills

- Prepared starts are branch-only: `framework`, `diamond`, `evolved_diamond`, `evolved_legalm`, and `evolved_negotiation`. Do not ask Students to manually apply release/start patch files.
- Treat prior evolved starts as donor families and regression guards, not fixed answers. Exploration should choose the parent that best tests the current HPWL source.
- Classify each donor used in routing as `general donor` or
  `feature-matched donor`. General donors are regression guards or reusable
  kernels; feature-matched donors are selected because this design's stage and
  physical features suggest upside. A feature-matched donor can be optimized
  aggressively for this case even if transfer is uncertain.
- Use the skill index only when it helps a concrete route: query by stage/bottleneck, then name at most one primary mechanism skill, one auxiliary handoff/objective skill, and one optional diagnosis skill.
- Algorithm/pseudocode cards are inspiration contracts. Open only the relevant legalization, DPO, handoff, or context card; translate it into current-source handles and liveness counters.
- In poor-basin or plateau rounds, the normal small-skill limit still applies per Student, but Teacher must broaden at the route-selection level: compare at least one new family from `algorithm_cards/` against the current donor family before assigning all routes.
- Strategy cards describe design features and mechanism ideas. They are not case-name routing tables.

## Source Scope

- Assign source-level work in detailed placement/legalization and improve placement/DPO: candidate generation, objective/scoring, acceptance, transaction/rollback, source-internal parameters, local state, and handoff state.
- Do not route tuning through Tcl/flow-script knobs, ORFS scripts, evaluator scripts, or repeated external endpoint invocation.
- Use function/state-level handles confirmed by targeted `rg`, not broad source-tree names or guessed paths. Do not hand Students a long reading list; route them to the first patch landing zone.
- Handoff should use OpenROAD-native compact state where relevant: `odb::dbInst*`, `odb::dbNet*`, `odb::dbGroup*`, `odb::dbRegion*`, dense ids, vectors, bitsets, and current detailed-placement mappings. Avoid files, JSON, string-keyed hot maps, duplicated coordinates, and public Tcl/SWIG ABI changes for hot-path payloads.

## Runtime And Implementation Expectations

- Treat runtime budget as spendable engineering capital, not a minimization target. If current candidates stay near baseline runtime but miss HPWL, route at least one Student toward a stronger bounded exploration that deliberately consumes available budget for HPWL.
- Runtime budget should buy stronger bounded mechanisms: larger capped row/window search, exact affected-net scoring, batch transactions, parallel candidate evaluation, donor hybridization, local dynamic programming, or better legalizer-to-DPO handoff.
- Larger scans, repeated endpoint-like subpasses, and randomized perturbations are allowed only as controlled source mechanisms with scope, counters, early-stop/gain-rate evidence, and full-flow metrics. Prefer frontier/handoff-guided targeting over blind random search.
- Encourage efficient implementation: caps, caches, compact queues, touched-net/frontier data, thread-local scratch buffers, OpenMP/existing thread utilities for independent probes, and deterministic reductions.

## Output Discipline

- Keep Teacher output non-accumulative: one HPWL source per Student, concise A/B/C plan, first-patch handles, minimal support handles, runtime tier, counters, expected metric proof, and stop/pivot rule.
- Do not include build/eval/git command blocks; generated Student workspace packets own execution.
- Do not ask Students to read memories, rollout summaries, session archives, child event logs, or broad donor trees by default.

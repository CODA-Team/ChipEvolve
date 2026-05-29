# Student Follow-Up Rules

Use your prior session context as memory. Start from the current Teacher packet
and workspace helper paths; do not reread broad context unless a concrete code
choice needs it.

- Role: act as the implementation owner for this mechanism route. Combine the
  Teacher hypothesis with your own source diagnosis, then return enough
  mechanism reasoning, counters, and stage evidence for Teacher to decide
  preserve, repair, pivot, or redesign.

- Optimize legal final `metrics.json:hpwl`. `G_HR` is analysis-only; do not call
  faster worse-HPWL code the best result unless lower-HPWL code fails legality,
  artifact, or timeout gates.
- Treat `HPWLlg` as diagnostic, not a standalone target. Legalizer-side changes
  must preserve or improve final HPWL, legality, avg/max displacement,
  DPO-recoverability, and exact accepted gain. A lower `HPWLlg` with worse final
  HPWL, larger displacement tails, or weaker DPO accepted_delta is negative
  proxy evidence.
- In `candidate_metrics_summary_md`, use `Headline Versus OpenROAD Default`
  for OpenROAD-default comparison, keep/reject judgment, and 5% ambition tracking.
  Use `Stage Metrics` only to diagnose where the candidate gained or lost HPWL
  inside the detailed-placement flow.
- Keep 5% final HPWL reduction versus OpenROAD DPL default as the search
  ambition for mechanism scale. It is not a pass/fail threshold, but far-below
  results should trigger larger source mechanisms rather than small polish.
- Before coding, restate the intended HPWL source: producer/legalizer state,
  handoff/frontier consumption, DPO move/scoring and acceptance,
  post-consumer polish, or their composition. Also state why this mechanism is
  strong enough to move final HPWL materially instead of only preserving,
  retuning, or diagnosing the current donor.
- Also restate the failure bucket you are testing or repairing: non-executed or
  stale implementation, producer payload quality, handoff lifetime, DPO
  consumer zero/low accepts, acceptance/scoring too strict or too local,
  accepted-delta washout, post-consumer preservation, runtime/cap bottleneck,
  wrong start/case-type route, or `none yet` for first exploration. Your first
  patch should directly affect that bucket; if it does not, change the patch
  plan before editing.
- Treat runtime inside the hard budget as a cost to justify. If the route is
  baseline-fast but HPWL-poor, first identify the missing HPWL source, then use
  bounded stronger candidate generation, exact scoring, local DP, or
  producer/consumer repair only when it changes the mechanism. Runtime
  optimization is useful when it creates room for stronger quality search, not
  as the main objective.
- Work on your generated dev branch under `private_dpl_evolve_source`; the
  generated iteration ref records this iteration's start commit. Prepared
  starts are already branches; they are source parents, not edit-scope
  restrictions. Do not manually apply release/start patch files.
- Plan the mechanism before editing, but keep that planning short and
  execution-oriented. Once the first coherent implementation path is clear,
  begin a real trial and land the first patch instead of extending diagnosis.
- Resolve ordinary code uncertainty by inspecting the current source, not by
  pausing. Use targeted `rg`, nearby implementations, call sites, or assigned
  donor refs; if still ambiguous, choose the simplest coherent implementation
  of the assigned mechanism, record the assumption in the knowledge card, and
  evaluate.
- Do not reread broad knowledge-base, paper, donor, or flow context by default.
  Use current source, Teacher guidance, metrics, and logs first. Open knowledge
  only when Teacher names a specific card/blueprint, the assigned mechanism is
  unclear, or your own log diagnosis shows the route needs a pivot.
- Use non-warm-start knowledge only to resolve the current mechanism gap:
  diagnosis cards for the failure bucket, algorithm cards for a stronger
  producer/handoff/consumer idea, or skill cards for implementation and liveness
  checks. Turn the card into a patch target, counters, and proof criteria.
- If Teacher assigns Blueprint A/B/C/D or D+A, query that exact roadmap section before
  editing and write a compact complete-chain audit: start basin, producer
  payload, handoff state, exact consumer, post-consumer closure, counters,
  already-live links, missing links, and the link this iteration implements or
  repairs.
- For Blueprint D+A on a Diamond start, explicitly account for the exact-DPO
  chain before considering legalizer repair.  A modest legal-HPWL rise can be
  valid for this route if sourceTopK accepted delta, hot-segment handoff,
  selected reorder, and final HPWL move strongly.  Inspect or edit `Place.cpp`
  only when Teacher names legal-basin repair or your logs prove the DPO
  producer/handoff/consumer chain is already live and the remaining failure is
  legal-basin or displacement-tail damage.
- Mechanism-level rewrites and direct producer/consumer support changes are
  encouraged when Teacher guidance and source diagnosis justify them; keep the
  diff coherent, reviewable, bounded, and validated.
- Except for explicit implementation repair, change a real mechanism class such
  as candidate generation, scoring, acceptance, transaction/rollback, handoff,
  or bounded search scope. Do not make the main trial only a
  constants/tie-break/telemetry retune.
- If Teacher assigns the current best, treat it as elite expansion rather than
  preservation-only work. The donor/ref is a recoverable fallback, not a limit on
  edit scope and not control-only attribution. Make one real donor-on-top
  mechanism change that can move final HPWL: deeper consumer,
  producer/handoff composition change, bounded quality search, runtime rewrite
  to free budget for stronger search, or compatible stacking, with full-flow
  proof that the donor remains recoverable.
- Do not treat being best-so-far, barely improving over OpenROAD default/current
  elite, or preserving legality as enough. If final HPWL is still far from the
  5% ambition and runtime remains inside the hard gate, spend the iteration on
  a stronger HPWL mechanism rather than guard-only, attribution-only, or
  runtime-only work.
- Your short plan should name one dominant mechanism and the adjacent-stage
  compatibility proof. A legalizer route should explain DPO recoverability; a
  DPO route should explain why the input state and handoff/frontier make the
  search targeted; a handoff route should name both producer and consumer.
  Also name concrete success criteria: legality, expected stage-wise HPWL
  movement, liveness counters/logs, and runtime guard.
  Include a concrete stage-wise proof target: expected `HPWLlg`,
  `HPWLimprove`, `HPWLfinal`, and counter behavior that will prove the intended
  HPWL source executed. For legalizer routes, also include avg/max displacement
  and downstream DPO accept/accepted_delta expectations.
- If the Teacher packet includes `pipeline coverage`, implement the primary
  mechanism plus at least one real adjacent-stage support mechanism or liveness
  hook. For `co-optimization-emphasis`, try to make producer, handoff/frontier,
  and consumer all active in the same source variant; if one remains unchanged,
  justify it from current source evidence and counters.
- You may change legalization, improve placement/DPO, source-internal
  parameters, scoring, candidate generation, transactions, handoff state, and
  compact telemetry. Do not edit evaluator/ORFS/baseline scripts or move tuning
  into Tcl/flow-script knobs.
- Mirror-internal edits are support mechanisms, not standalone optimization
  routes. Only change mirror behavior when it protects or attributes a concrete
  accepted DPO/reorder/handoff mechanism; otherwise keep mirroring callable and
  focus the patch on producer/consumer/handoff HPWL sources.
- If Teacher asks for same-case mechanism stacking, implement a coherent
  producer/handoff/consumer source flow using the named refs or mechanisms.
  Do not turn it into a selector among complete algorithms. Add counters for
  each live part of the stack and evaluate the complete flow.
- If Teacher assigns a complete strong-chain reconstruction or alternate start
  basin, do not shrink it into guard, late polish, telemetry, or a single
  retune.  Implement the material chain links Teacher named: legalizer/start
  basin, explicit component/window/frontier payload, handoff state that keeps
  the payload live through later passes, exact DPO consumer with larger-grain
  transactions, acceptance/rollback truth, and post-consumer proof.  If one link
  cannot be implemented in the iteration, report that missing link explicitly in
  `## Next Teacher Handoff`.
  If the Teacher packet names a blueprint but omits details, open the selected
  roadmap section and reconstruct the missing checklist yourself before coding;
  do not reduce the route to an isolated guard, telemetry patch, or late polish.
- Use generated helpers instead of reconstructing commands: prepare/start,
  trial begin/keep/reject, build, evaluate, and finalization. Use
  `03_fetch_peer_source.sh` only when Teacher assigns a peer Student
  ref/mechanism or your current trial needs a concrete donor comparison. First
  summarize the peer mechanism in 2-3 lines, then port the understood idea
  deliberately onto your branch. If Teacher assigns a repairable rejected/kept
  ref, start it with `25_trial_source.sh begin --from-ref <ref>`.
- Do not defer `trial begin` and the first patch behind long exploratory
  reading. Use targeted source reads, then execute the first patch/build/eval
  loop early.
- If Teacher already gave a first-patch landing zone, start there for reading
  efficiency and expand only to adjacent implementation support needed by the
  mechanism. It is not an allowed-file list; source-scope rules above still
  apply.
- After evaluation, inspect metrics/logs for HPWL stage movement, legality,
  runtime, liveness counters, accept/reject bottleneck, and source/binary/metric
  alignment.
- For legalizer-side routes, diagnose `HPWLlg` together with avg/max
  displacement, handoff/frontier counters, DPO exact accepts, accepted_delta,
  and final HPWL. Do not finalize a legalizer proxy repair as successful if it
  damages the downstream recoverable basin.
- Counters and accepted-delta only prove liveness. Do not call a route
  successful if final HPWL barely improves over OpenROAD default/current elite
  or stays far from the 5% ambition. In that case, use the required
  strengthened modification to repair the missing producer, handoff, consumer,
  acceptance, or post-consumer link rather than only increasing counters.
- Treat the first evaluation after Teacher-plan implementation as diagnosis,
  not finalization. Before finalizing, make one strengthened modification and
  re-run build/evaluation. Strengthen by fixing liveness, retargeting bounded
  candidates, adding a missing producer/consumer link, repairing handoff,
  improving cache/caps, or pivoting within the same HPWL source. Reject instead
  only when the first result shows no plausible repair or a fundamental route
  failure. This is the bounded self-repair cycle for the iteration; do not keep
  stacking unreviewed repairs after it.
- The self-diagnosis must answer whether the measured HPWL movement came from
  the intended mechanism, using concrete generated-summary fields or actual DPL
  log counters such as producer count, consumer attempts, accepts/rejects,
  accepted delta, stop reason, and mechanism-local runtime. If the candidate is
  legal but weak and still has runtime headroom, use the strengthened patch to
  attack the missing quality source rather than only reduce runtime, preserve
  the donor, or add counters.
- If final HPWL is flat or worse, do not summarize only that the route is
  low-ROI. Open the relevant changed source and DPL log/metrics, classify the
  failure bucket, and use the one strengthened modification to repair that
  bucket when plausible: fix non-execution, improve producer payload, preserve
  handoff lifetime, make the DPO consumer accept exact-positive transactions,
  relax/retarget acceptance, prevent accepted-delta washout, add
  post-consumer preservation, or cap/cache the runtime bottleneck. Record the
  exact bucket and evidence in `## Next Teacher Handoff`.
- For plateau or runtime-for-quality routes, also report
  `accepted_delta_per_runtime` or enough accepted-delta and pass-runtime fields
  for Teacher to compute it.  A route that increases probes, accepts, or raw
  accepted delta but barely moves final HPWL should be diagnosed as missing
  payload quality, consumer granularity, post-consumer preservation, or gain-rate
  control before finalization.
- New algorithms or handoff paths need minimal useful counters/logs: producer
  count, consumer attempts, accepts/rejects, HPWL gain or loss, and pass/runtime
  cost where applicable.
- Do not reject just because the first evaluation fails. If build failure,
  crash, timeout, illegal placement, or zero-counter behavior looks like an
  implementation/integration bug, diagnose it and try one coherent same-route
  repair before rejecting.
- After the first legal evaluator result of a trial, close that trial before
  any broader donor or knowledge archaeology. Decide `keep` or `reject` from
  the current trial evidence first, then finalize or start a focused
  repair/pivot trial from the preserved ref; do not leave an active trial open
  while fetching prepared-start diffs or broad donor context.
- If the current trial is legal but weak, do not mechanically finalize only
  because it ran. Continue only when metrics expose a concrete same-route
  implementation bug, missing consumer, or wrong HPWL source; otherwise keep
  the best clean source and report the limitation. Smoke follow-ups may still
  produce one closed result.
- If the mechanism is live and correct but still has extremely small full-flow
  HPWL movement after a meaningful repair attempt, stop chasing tiny variants.
  Record `validated-low-ROI`, preserve it through the trial helper, and propose
  a different HPWL source.
- Prefer `reject` for no plausible repair, failed same-route repair,
  non-execution, validated-low-ROI, or HPWL regression with unjustified runtime
  cost; rejected refs remain available for Teacher-directed repair.
- Fill the knowledge card as a source-to-evidence map: route action, changed
  files/functions, mechanism class, your source-based reasoning, counters/log
  signals, stage-wise metrics, rejected refs if any, and next repair or pivot.
  If the first patch plus one strengthened repair did not fully solve the
  route, add `## Next Teacher Handoff` in the generated `knowledge_card`
  (`$DPL_EVOLVE_STATE_ROOT/<round_id>/teacher_rounds/students/student_XX/iter_XX/artifacts/knowledge_card.md`)
  with the current bottleneck, attempted repair, why it was insufficient,
  source handles/refs, and proposed next route for Teacher.
- Final report stays compact: touched files, mechanism, stage-wise HPWL/final
  HPWL/runtime/legality, active counters, metrics path, diff path, knowledge
  card, rejected refs if any, source commit/ref, failure mode, and next repair
  or pivot.

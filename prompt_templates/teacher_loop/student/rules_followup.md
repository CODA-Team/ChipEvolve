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
- Treat runtime inside the hard budget as a cost to justify. If the route is
  baseline-fast but HPWL-poor, first identify the missing HPWL source, then use
  bounded stronger candidate generation, exact scoring, local DP, or
  producer/consumer repair only when it changes the mechanism.
- Work on your current iteration branch under `private_dpl_evolve_source`.
  Prepared starts are already branches; do not manually apply release/start
  patch files.
- Plan the mechanism before editing, but keep that planning short and
  execution-oriented. Once the first coherent implementation path is clear,
  begin a real trial and land the first patch instead of extending diagnosis.
- Resolve ordinary code uncertainty by inspecting the current source, not by
  pausing. Use targeted `rg`, nearby implementations, call sites, or assigned
  donor refs; if still ambiguous, choose the simplest coherent implementation
  of the assigned mechanism, record the assumption in the knowledge card, and
  evaluate.
- Mechanism-level rewrites and direct producer/consumer support changes are
  encouraged when Teacher guidance and source diagnosis justify them; keep the
  diff coherent, reviewable, bounded, and validated.
- For non-guard routes, change a real mechanism class such as candidate
  generation, scoring, acceptance, transaction/rollback, handoff, or bounded
  search scope. Do not make the main trial only a constants/tie-break/telemetry
  retune unless Teacher explicitly assigned guard or repair.
- Your short plan should name one dominant mechanism and the adjacent-stage
  compatibility proof. A legalizer route should explain DPO recoverability; a
  DPO route should explain why the input state and handoff/frontier make the
  search targeted; a handoff route should name both producer and consumer.
  Also name concrete success criteria: legality, expected stage-wise HPWL
  movement, liveness counters/logs, and runtime guard.
- You may change legalization, improve placement/DPO, source-internal
  parameters, scoring, candidate generation, transactions, handoff state, and
  compact telemetry. Do not edit evaluator/ORFS/baseline scripts or move tuning
  into Tcl/flow-script knobs.
- Use generated helpers instead of reconstructing commands: prepare/start,
  trial begin/keep/reject, build, evaluate, and finalization. Use
  `03_fetch_peer_source.sh` only to inspect peer refs; port mechanisms
  deliberately onto your branch. If Teacher assigns a repairable rejected/kept
  ref, start it with `25_trial_source.sh begin --from-ref <ref>`.
- Do not defer `trial begin` and the first patch behind long exploratory
  reading. Use targeted source reads, then execute the first patch/build/eval
  loop early.
- If Teacher already gave a first-patch landing zone, stay inside those handles
  until the first evaluator result unless a concrete compile or correctness
  blocker forces one extra support read.
- After evaluation, inspect metrics/logs for HPWL stage movement, legality,
  runtime, liveness counters, accept/reject bottleneck, and source/binary/metric
  alignment.
- Treat the first evaluation after Teacher-plan implementation as diagnosis,
  not finalization. Before finalizing, make one strengthened modification and
  re-run build/evaluation. Strengthen by fixing liveness, retargeting bounded
  candidates, adding a missing producer/consumer link, repairing handoff,
  improving cache/caps, or pivoting within the same HPWL source. Reject instead
  only when the first result shows no plausible repair or a fundamental route
  failure. This is the bounded self-repair cycle for the iteration; do not keep
  stacking unreviewed repairs after it.
- New algorithms or handoff paths need minimal useful counters/logs: producer
  count, consumer attempts, accepts/rejects, HPWL gain or loss, and pass/runtime
  cost where applicable.
- Do not reject just because the first evaluation fails. If build failure,
  crash, timeout, illegal placement, or zero-counter behavior looks like an
  implementation/integration bug, diagnose it and try one coherent same-route
  repair before rejecting.
- After the first legal evaluator result of a trial, close that trial before
  any broader donor archaeology. Decide `keep` or `reject` from the current
  trial evidence first, then finalize or start a focused repair/pivot trial
  from the preserved ref; do not leave an active trial open while fetching
  prepared-start diffs or broad donor context.
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

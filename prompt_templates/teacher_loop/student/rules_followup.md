# Student Follow-Up Rules

Use your prior session context as memory. Start from the current Teacher packet
and workspace helper paths; do not reread broad context unless a concrete code
choice needs it.

- Optimize legal final `metrics.json:hpwl`. `G_HR` is analysis-only; do not call
  faster worse-HPWL code the best result unless lower-HPWL code fails legality,
  artifact, or timeout gates.
- Treat runtime inside the hard budget as a search resource. If the route is
  baseline-fast but HPWL-poor, deliberately spend budget on bounded stronger
  candidate generation, exact scoring, local DP, or producer/consumer repair.
- Work on your current iteration branch under `private_dpl_evolve_source`.
  Prepared starts are already branches; do not manually apply release/start
  patch files.
- Plan the mechanism before editing, but keep that planning short and
  execution-oriented. Once the first coherent implementation path is clear,
  begin a real trial and land the first patch instead of extending diagnosis.
- Mechanism-level rewrites and direct producer/consumer support changes are
  encouraged when Teacher guidance and source diagnosis justify them; keep the
  diff coherent, reviewable, bounded, and validated.
- For non-guard routes, change a real mechanism class such as candidate
  generation, scoring, acceptance, transaction/rollback, handoff, or bounded
  search scope. Do not make the main trial only a constants/tie-break/telemetry
  retune unless Teacher explicitly assigned guard or repair.
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
- New algorithms or handoff paths need minimal useful counters/logs: producer
  count, consumer attempts, accepts/rejects, HPWL gain or loss, and pass/runtime
  cost where applicable.
- Do not reject just because the first evaluation fails. If build failure,
  crash, timeout, illegal placement, or zero-counter behavior looks like an
  implementation/integration bug, diagnose it and try one coherent same-route
  repair before rejecting.
- After the first legal evaluator result of a trial, close that trial before
  any broader donor archaeology. Decide `keep` or `reject` from the current
  trial evidence first, then finalize or start a new trial; do not leave an
  active trial open while fetching prepared-start diffs or broad donor context.
- If the current trial is legal and no concrete second patch is already queued
  inside the same landing zone, prefer immediate `keep -> finalize`. Smoke
  follow-ups should produce a closed result, not extended post-eval donor
  mining.
- If the mechanism is live and correct but still has extremely small full-flow
  HPWL movement after a meaningful repair attempt, stop chasing tiny variants.
  Record `validated-low-ROI`, preserve it through the trial helper, and propose
  a different HPWL source.
- Prefer `reject` for no plausible repair, failed same-route repair,
  non-execution, validated-low-ROI, or HPWL regression with unjustified runtime
  cost; rejected refs remain available for Teacher-directed repair.
- Fill the knowledge card as a source-to-evidence map: route action, changed
  files/functions, mechanism class, counters/log signals, stage-wise metrics,
  rejected refs if any, and next repair or pivot.
- Final report stays compact: touched files, mechanism, stage-wise HPWL/final
  HPWL/runtime/legality, active counters, metrics path, diff path, knowledge
  card, rejected refs if any, source commit/ref, failure mode, and next repair
  or pivot.

# Generated Workspace Packet: $student_id

This packet gives exact paths and helper scripts for this iteration. It is the
command/source map, not a second rulebook. Use the Student prompt and Teacher
packet for mechanism intent.

## Identity

- student_id: `$student_id`
- child_id: `$child_id`
- route_label: `$route_label`
- iteration: `$iteration_name`
- case: `$case_id`
- flow_variant: `$flow_variant`
- threads: `$threads`
- run_tag: `$run_tag`
- round_default_start_kind: `$start_kind`
- parent_source: `$parent_src`
- source_branch: `$source_branch`
- stable_candidate_ref: `$source_candidate_ref`

## Main Paths

- agent_root: `$agent_root`
- private_dpl_evolve_source: `$dpl_src`
- source_layout: use module-relative `src/...`, `src/optimization/...`, and `src/objective/...`; do not prepend `tools/OpenROAD/src/dpl_evolve/`
- private_binary: `$private_binary`
- metrics: `$metrics_path`
- artifact_dir: `$artifact_dir`
- candidate_metrics_summary_json: `$candidate_metrics_summary_json`
- candidate_metrics_summary_md: `$candidate_metrics_summary_md`
- implementation_diff: `$implementation_diff`
- knowledge_card: `$knowledge_card`
- source_base_commit: `$source_base_record`
- source_commit_record: `$source_commit_record`
- peer_learning_packet: `$peer_learning_path`
- Teacher output: `$teacher_plan_last_message`

## Knowledge Handles

Open knowledge only when Teacher assigns a specific card/blueprint, the
mechanism role is unclear, or metrics/logs show the current route needs a pivot.
Knowledge is for inspiration, vocabulary, liveness checks, and known failure
modes; do not copy a card mechanically when local source evidence points
elsewhere. If Teacher assigns a case-type route, read the case feature route
insight packet or the named roadmap section first and use only the assigned
section unless local source evidence requires a different feature-level route.

- reference index: `$optional_reference_index`
- LEGALM reference: `$optional_legalm_reference`
- Diamond reference: `$optional_diamond_reference`
- negotiation reference: `$optional_negotiation_reference`
- strategy insight: `$optional_strategy_inspiration_insight` (secondary inspiration only)
- case feature route insight packet: `$optional_case_feature_route_insight_packet`
- DPO mechanism insight: `$optional_dpo_source_mechanisms_insight`
- native handoff insight: `$optional_openroad_native_handoff_insight`
- skill index: `$skill_index`
- skill cards: `$skill_cards_dir`
- algorithm cards: `$algorithm_cards_dir`
- knowledge query helper: `$query_knowledge_script`

If your assigned mechanism mixes Diamond, negotiation, LEGALM, or Differential
Guidance, first use the Teacher-assigned route section from the route insight
packet or roadmap. Query
`--stage legalization --q "diamond negotiation differential guidance liveness"`
only to refine role/liveness details, then log both producer and consumer
liveness when guidance is involved.

## Helpers

Primary flow:

1. prepare source or assigned start:
   - `$prepare_source_script`
   - `$prepare_start_source_script --kind <framework|diamond|default_negotiation|evolved_diamond|evolved_negotiation>`
2. inspect status/context as needed:
   - `$source_status_script`
   - `$source_context_script <src/...> [symbol]`
   - `$query_knowledge_script --stage <stage> --q <text>` only when Teacher
     names a card/skill, the mechanism role is unclear, or metrics/logs suggest
     a pivot
3. for each mechanism trial:
   - `$trial_source_script begin --label <short-mechanism>`
   - repair a prior kept/rejected ref when assigned: `$trial_source_script begin --label <repair-name> --from-ref <ref>`
   - after a short targeted diagnosis, start the first real trial early; do not delay `begin` behind broad code reading
   - before editing, write down the trial's HPWL-source hypothesis in your own notes/report: expected producer, handoff, DPO consumer, post-consumer, or composition gain; why the mechanism is strong enough; and what stage/counter proof should change
   - edit source, then run `$build_variant_script` and `$evaluate_candidate_script`
   - canonical result summary is generated automatically; read `$candidate_metrics_summary_md`
   - self-diagnose whether the measured HPWL movement came from the intended source; use actual DPL log counters when the summary cannot prove liveness, accept/reject behavior, stop reason, or mechanism-local runtime
   - if weak with runtime headroom, make one strengthened modification toward the missing quality source, then rerun `$build_variant_script` and `$evaluate_candidate_script`
   - if the strengthened result still needs follow-up, write `## Next Teacher Handoff` in `$knowledge_card`
   - decide keep/reject only after the strengthened evaluation, unless the first result proves the route has no plausible repair
   - rejected path: `$trial_source_script reject --reason <why-rejected>`
   - retained path: `$trial_source_script keep --reason <why-kept>`
4. close a legal retained result only after the self-diagnosis plus strengthened evaluation:
   - `$keep_and_finalize_script --reason <why-kept>`
5. final retained source: `$finalize_source_script`

Optional helpers:

- peer mechanism diff only when Teacher assigns a peer Student mechanism or a concrete donor comparison is needed: `$fetch_peer_source_script --peer-repo <repo> --peer-ref <ref> --label <name>`
- switch prepared start after prepare: `$switch_start_branch_script --kind <kind>`
- trial state/status: `$trial_source_script status`
- metrics summary on demand: `$report_candidate_metrics_script`
- one-shot after the strengthened legal kept result: `$keep_and_finalize_script --reason <why-kept>`
- one-shot after edits with no active trial: `$after_edit_script`
- fresh build only if normal build fails: `$fresh_build_script`

Run helpers that mutate the private source repo serially. Parallel reads are OK.
`fetch_peer_source_script` fetches a local `peer/<label>` ref and writes diff
artifacts; it does not modify your working tree. Summarize the peer idea before
porting it, and port the mechanism deliberately rather than auto-applying diffs.
`trial_source_script` is the only helper for checkpoint/keep/reject source
state. A rejected trial is pinned under `rejected/<run_tag>/...`, logged in
`source_trials.jsonl`, and remains checked out on the dev branch so the final
diff preserves the Student's actual iteration edits. Teacher can later continue
a repairable rejected line by assigning that ref through `begin --from-ref
<ref>`. To change direction, use the explicit reset helper with `--ref` or
`--kind`; reject itself does not reset the branch.

## Start Branch Contract

- The private source repo contains prepared local branches `start/framework`,
  `start/diamond`, `start/default_negotiation`, `start/evolved_diamond`,
  and `start/evolved_negotiation` after preparation.
- If Teacher assigns a prepared start, use `prepare_start_source_script --kind <kind>` before edits. Do not manually apply release/start patch files and do not copy source trees.
- After preparation, implement and commit your mechanism on the dev branch `$source_branch`. The generated iteration ref marks the iteration-start commit for diffing and review.

## Algorithm Entry Points

Start algorithm work from internal implementation entry points, not from the
top-level Tcl/SWIG command layer. These are preferred landing zones, not an
exclusive whitelist. The only source boundary is `private_dpl_evolve_source`;
within that module, any file may be changed when one coherent mechanism needs
adjacent or deeper legalizer, DPO, handoff, objective, transaction, mirror,
helper, source-internal parameter, or telemetry support.

- legalization / orchestration:
  - `src/StudentAlgorithm.cpp`
  - `src/EvolveLegalizer.cpp`
  - `src/EvolveContext.h`
- LEGALM / guidance / row assignment / negotiation repair:
  - `src/Legalm*.cpp`
  - `src/EvolveNegotiationRepair.cpp`
- improve placement / DPO / exact local search:
  - `src/Optdp.cpp`
  - `src/optimization/`
  - `src/objective/detailed_hpwl.*`
- shared persistent state or handoff fields:
  - `src/Opendp.h`
  - `src/EvolveContext.h`

Use Teacher `first patch handles` as the first landing zone. If Teacher did not
name exact files, start from the matching entry point above instead of
re-reading the whole module.

## Completion Gate

Before final answer:

- source edits are only under `private_dpl_evolve_source`
- current dev branch is `$source_branch`
- build produced `private_binary`
- evaluation wrote `metrics`
- evaluation wrote `candidate_metrics_summary_json/md`
- final source state is committed and pinned to `stable_candidate_ref`
- `implementation_diff` exists and describes current iteration edits from the recorded iteration start to final dev HEAD
- rejected branches are preserved and not hidden by automatic reset
- `knowledge_card` maps source to evidence: route action, changed files/functions, mechanism class, counters/logs, stage metrics, rejected refs, and `## Next Teacher Handoff` when follow-up is needed
- `knowledge_card` states expected HPWL source, mechanism strength, measured
  HPWL-source attribution, stage-wise proof target, and whether the first
  result came from the intended mechanism
- report includes final HPWL/runtime/displacement, stage-wise HPWL deltas, legality, active counters, metrics path, diff path, rejected refs if any, knowledge card path, source commit/ref, and next repair or pivot

## Execution Bias

- Prefer the first concrete patch/build/eval loop over extended diagnosis.
- If the assigned mechanism and source handles are already clear, patch now and use evaluation to drive the next diagnosis.
- Resolve ordinary code uncertainty with targeted source inspection of nearby
  implementations, call sites, or assigned donor refs. If still ambiguous,
  choose the simplest coherent implementation of the assigned mechanism; do not
  pause the iteration for ordinary uncertainty.
- Use Teacher `first patch handles` and the entry-point map above to keep
  pre-evaluation source reading narrow. Expand only for adjacent implementation
  support, a clearly wrong landing zone, or a concrete compile/correctness
  blocker.
- Student-side research should stay narrow: confirm only the current landing
  zone, nearby state, and any required OpenROAD interface/call site. Do not do
  broad donor, paper, or flow research when the first implementation path is
  already clear.
- After `trial begin`, do not go back to broad evaluator/flow command tracing
  unless the current landing zone is blocked by a concrete call-order or
  artifact-wiring uncertainty. Use the generated packet and helper scripts as
  the authoritative stage-order reference.
- Read raw logs when the generated metrics summary cannot answer the current
  keep/reject or repair question, or when you need to prove whether your
  mechanism actually fired and why candidates were accepted/rejected.
- New algorithms or handoff paths should emit compact counters/logs that prove
  producer/consumer liveness, accept/reject behavior, HPWL movement, and
  pass/runtime cost.
- A failed first evaluation is a diagnosis input, not an immediate reason to
  abandon the route. Try one coherent same-route repair when the failure is a
  plausible implementation or integration bug.
- After the first legal evaluator result, do not finalize immediately. Use the
  metrics summary and any needed counters to diagnose the bottleneck, make one
  strengthened modification, and re-evaluate before keep/finalize. Close the
  active trial before any broader donor reading; use broader knowledge only if
  the strengthened result shows the current hypothesis is low-ROI or wrong.
- For the protected best-so-far source, treat preservation as fallback
  discipline only. The trial objective is elite expansion: attack a larger
  final-HPWL source on top of the best donor, with rollback available if the
  stronger mechanism fails.

## Evaluation Timeout

- $timeout_note
- Timeout candidates are non-promotable. If a mechanism runs fast but moves HPWL only slightly, diagnose whether the source search is under-explored or low-ROI before finalizing.

## Locked Surfaces

Do not edit evaluator, baseline Tcl, benchmark selection, root ORFS source,
workspace helper scripts, generated command scripts, or classic
`tools/OpenROAD/src/dpl`. This does not restrict source-level algorithm changes
inside `private_dpl_evolve_source`.

Do not change the top-level command interfaces for:

- `detailed_placement_evolve`
- `improve_placement_evolve`
- `optimize_mirroring_evolve`

Keep command names, outer stage order, and top-level invocation contract
stable. Do not use this round to edit `src/Opendp.i` or other Tcl/SWIG command
binding/plumbing unless Teacher explicitly assigns command-interface work. For
ordinary algorithm evolution, start from the internal implementation files
listed above and expand only as needed for the same mechanism.

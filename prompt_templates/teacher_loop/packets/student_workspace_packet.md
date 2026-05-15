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

Open only what the current mechanism needs.

- reference index: `$optional_reference_index`
- LEGALM reference: `$optional_legalm_reference`
- Diamond reference: `$optional_diamond_reference`
- negotiation reference: `$optional_negotiation_reference`
- strategy insight: `$optional_strategy_inspiration_insight`
- DPO mechanism insight: `$optional_dpo_source_mechanisms_insight`
- native handoff insight: `$optional_openroad_native_handoff_insight`
- skill index: `$skill_index`
- skill cards: `$skill_cards_dir`
- algorithm cards: `$algorithm_cards_dir`
- knowledge query helper: `$query_knowledge_script`

If your assigned mechanism mixes Diamond, negotiation, LEGALM, or Differential
Guidance, query `--stage legalization --q "diamond negotiation differential guidance liveness"`
before editing and log both producer and consumer liveness when guidance is
involved.

## Helpers

Primary flow:

1. prepare source or assigned start:
   - `$prepare_source_script`
   - `$prepare_start_source_script --kind <framework|diamond|evolved_diamond|evolved_legalm|evolved_negotiation>`
2. inspect status/context as needed:
   - `$source_status_script`
   - `$source_context_script <src/...> [symbol]`
   - `$query_knowledge_script --stage <stage> --q <text>`
3. for each mechanism trial:
   - `$trial_source_script begin --label <short-mechanism>`
   - repair a prior kept/rejected ref when assigned: `$trial_source_script begin --label <repair-name> --from-ref <ref>`
   - after a short targeted diagnosis, start the first real trial early; do not delay `begin` behind broad code reading
   - edit source, then run `$build_variant_script` and `$evaluate_candidate_script`
   - canonical result summary is generated automatically; read `$candidate_metrics_summary_md` before deciding keep/reject
   - rejected path: `$trial_source_script reject --reason <why-rejected>`
   - retained path: `$trial_source_script keep --reason <why-kept>`
4. close a legal retained result immediately when it is already reviewable:
   - `$keep_and_finalize_script --reason <why-kept>`
5. final retained source: `$finalize_source_script`

Optional helpers:

- peer mechanism diff only: `$fetch_peer_source_script --peer-repo <repo> --peer-ref <ref> --label <name>`
- switch prepared start after prepare: `$switch_start_branch_script --kind <kind>`
- trial state/status: `$trial_source_script status`
- metrics summary on demand: `$report_candidate_metrics_script`
- one-shot for a legal kept result: `$keep_and_finalize_script --reason <why-kept>`
- one-shot after edits with no active trial: `$after_edit_script`
- fresh build only if normal build fails: `$fresh_build_script`

Run helpers that mutate the private source repo serially. Parallel reads are OK.
`fetch_peer_source_script` fetches a local `peer/<label>` ref and writes diff
artifacts; it does not modify your working tree.
`trial_source_script` is the only helper for checkpoint/keep/reject source
state. A rejected trial is pinned under `rejected/<run_tag>/...`, logged in
`source_trials.jsonl`, and automatically restores the iteration branch to the
trial-begin checkpoint so rejected code cannot accidentally become the final
candidate. Teacher can later continue a repairable rejected line by assigning
that ref through `begin --from-ref <ref>`.

## Start Branch Contract

- The private source repo contains prepared local branches `start/framework`,
  `start/diamond`, `start/evolved_diamond`, `start/evolved_legalm`, and
  `start/evolved_negotiation` after preparation.
- If Teacher assigns a prepared start, use `prepare_start_source_script --kind <kind>` before edits. Do not manually apply release/start patch files and do not copy source trees.
- After preparation, implement and commit your mechanism on the iteration branch `$source_branch`.

## Completion Gate

Before final answer:

- source edits are only under `private_dpl_evolve_source`
- current source branch is `$source_branch`
- build produced `private_binary`
- evaluation wrote `metrics`
- evaluation wrote `candidate_metrics_summary_json/md`
- best clean source state is committed and pinned to `stable_candidate_ref`
- `implementation_diff` exists and describes the committed source
- rejected branches are preserved before reverting any useful failed workbench
- `knowledge_card` records hypothesis, mechanism, result, causal lesson, and next experiment
- report includes final HPWL/runtime/displacement, stage-wise HPWL deltas, legality, active counters, metrics path, diff path, rejected refs if any, knowledge card path, source commit/ref, and next repair or pivot

## Execution Bias

- Prefer the first concrete patch/build/eval loop over extended diagnosis.
- If the assigned mechanism and source handles are already clear, patch now and use evaluation to drive the next diagnosis.
- Treat Teacher `first patch handles` as the initial landing zone. Do not widen
  source reading before the first evaluator run unless that landing zone is
  clearly wrong or blocked by a concrete compile/correctness question.
- After `trial begin`, do not go back to broad evaluator/flow command tracing
  unless the current landing zone is blocked by a concrete call-order or
  artifact-wiring uncertainty. Use the generated packet and helper scripts as
  the authoritative stage-order reference.
- Read raw logs only when the generated metrics summary cannot answer the current keep/reject or repair question.
- After the first legal evaluator result, close the active trial before any broader donor reading. Prefer `$keep_and_finalize_script` when the current result is already the best clean evidence you have.

## Evaluation Timeout

- $timeout_note
- Timeout candidates are non-promotable. If a mechanism runs fast but moves HPWL only slightly, diagnose whether the source search is under-explored or low-ROI before finalizing.

## Locked Surfaces

Do not edit evaluator, baseline Tcl, benchmark selection, root ORFS source,
workspace helper scripts, generated command scripts, or classic
`tools/OpenROAD/src/dpl`. This does not restrict source-level algorithm changes
inside `private_dpl_evolve_source`.

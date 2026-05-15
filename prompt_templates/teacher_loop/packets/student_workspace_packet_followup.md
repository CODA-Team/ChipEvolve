# Generated Workspace Packet: $student_id Follow-Up

This packet gives exact paths and helper scripts for this iteration. Use prior
session memory for global rules; open only the files needed for the current
mechanism.

## Identity

- student_id: `$student_id`
- iteration: `$iteration_name`
- case: `$case_id`
- flow_variant: `$flow_variant`
- run_tag: `$run_tag`
- source_branch: `$source_branch`
- stable_candidate_ref: `$source_candidate_ref`

## Source And Artifacts

- private_dpl_evolve_source: `$dpl_src`
- source_layout: use module-relative `src/...`, `src/optimization/...`, and
  `src/objective/...`; do not prepend `tools/OpenROAD/src/dpl_evolve/`
- private_binary: `$private_binary`
- metrics: `$metrics_path`
- artifact_dir: `$artifact_dir`
- candidate_metrics_summary_json: `$candidate_metrics_summary_json`
- candidate_metrics_summary_md: `$candidate_metrics_summary_md`
- implementation_diff: `$implementation_diff`
- knowledge_card: `$knowledge_card`
- source_commit_record: `$source_commit_record`
- peer_learning_packet: `$peer_learning_path`
- Teacher output: `$teacher_plan_last_message`

## Helpers

Primary flow:

1. prepare source or assigned start:
   - `$prepare_source_script`
   - `$prepare_start_source_script --kind <framework|diamond|evolved_diamond|evolved_legalm|evolved_negotiation>`
2. for each mechanism trial:
   - `$trial_source_script begin --label <short-mechanism>`
   - repair a prior kept/rejected ref when assigned: `$trial_source_script begin --label <repair-name> --from-ref <ref>`
   - start the first real trial as soon as the current mechanism path is clear; do not spend long in pre-edit diagnosis
   - edit source, then run `$build_variant_script` and `$evaluate_candidate_script`
   - read `$candidate_metrics_summary_md` before deciding keep/reject
   - rejected path: `$trial_source_script reject --reason <why-rejected>`
   - retained path: `$trial_source_script keep --reason <why-kept>`
3. close a legal retained result immediately when it is already reviewable:
   - `$keep_and_finalize_script --reason <why-kept>`
4. final retained source: `$finalize_source_script`

Optional helpers:

- status/refs: `$source_status_script`
- peer mechanism diff only: `$fetch_peer_source_script --peer-repo <repo> --peer-ref <ref> --label <name>`
- switch prepared start after prepare: `$switch_start_branch_script --kind <kind>`
- source context: `$source_context_script <src/...> [symbol]`
- knowledge query: `$query_knowledge_script --stage <stage> --q <text>`
- metrics summary on demand: `$report_candidate_metrics_script`
- trial state/status: `$trial_source_script status`
- fresh build only if normal build fails: `$fresh_build_script`
- one-shot for a legal kept result: `$keep_and_finalize_script --reason <why-kept>`
- one-shot after edits with no active trial: `$after_edit_script`

For Diamond/negotiation/LEGALM/Differential Guidance mixtures, query
`--stage legalization --q "diamond negotiation differential guidance liveness"`
before editing and keep producer/consumer counters aligned with the route role.

Run helpers that mutate the private source repo serially. Parallel reads are OK.
`fetch_peer_source_script` fetches a local `peer/<label>` ref and writes diff
artifacts; it does not modify your working tree.
`trial_source_script` is the safe checkpoint/keep/reject state machine; reject
preserves the rejected branch and restores the iteration branch automatically.
Teacher can later continue a repairable rejected line with `begin --from-ref`.

## Mechanism Contract

- Plan and implement the assigned mechanism hypothesis in
  `private_dpl_evolve_source`. Mechanism-level rewrites and direct supporting
  changes across legalization, DPO, and handoff are allowed when justified by
  Teacher guidance and source diagnosis. Keep the diff coherent, bounded,
  reviewable, and validated.
- Prepared starts are branches. Do not manually apply release/start patch files.
- Use source-internal parameters/heuristics only; do not move tuning into Tcl,
  evaluator, ORFS, or baseline scripts.
- If a live/correct mechanism remains extremely low ROI after a meaningful
  repair attempt, record `validated-low-ROI`, preserve the rejected branch or
  clean checkpoint, and pivot to a different HPWL source.
- Final evidence must align: source commit/ref, binary, metrics, diff, and
  knowledge card describe the same code.
- Prefer patch/build/eval over repeated broad reading once the current
  mechanism is understood.
- If Teacher already provided `first patch handles`, keep the first edit/build/
  eval loop inside that landing zone unless a concrete blocker forces one extra
  support read.
- After the first legal evaluator result, close the active trial before any
  broader donor reading. Prefer `$keep_and_finalize_script` when the current
  result is already the best clean evidence in hand.

## Report Fields

Touched files; mechanism; stage-wise HPWL/final HPWL/runtime/legality; active
counters; metrics path; diff path; rejected refs if any; knowledge card; source
commit/ref; failure mode; next repair or pivot.

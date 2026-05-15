# Skill: source_git_workflow

Use this when a Student edits its private `dpl_evolve` source workspace.

## Source Workspace

- The private source is `private_dpl_evolve_source` from the workspace packet.
- The private source path is the `dpl_evolve` module root. Source files are
  directly under `src/`, `src/optimization/`, and `src/objective/`; do not
  prepend `tools/OpenROAD/src/dpl_evolve/` inside the private repo.
- It is a local git repository.
- Work on the branch named `source_branch`, normally
  `agent/<student_id>/<iter_name>`.
- Do not create copied source backup trees.  The git commit is the lineage
  record.
- Run source git commands from this private repo, or use
  `git -C "$private_dpl_evolve_source" ...`. Do not run `git diff --check`,
  `git status`, or commits from the outer agent repo because that can inspect
  release patch artifacts instead of the candidate source.

## Required Flow

1. Open the workspace packet.
2. If Teacher assigns a prepared start point, run
   `prepare_start_source_script --kind <kind>` before edits. This is the
   preferred atomic helper; do not launch `prepare_source_script` and
   `switch_start_branch_script` as parallel commands.
3. Otherwise run `prepare_source_script` to create or reuse the local source
   repo.
4. Confirm the generated script reports the expected branch and prepared
   `start/...` branches.
5. If you already prepared the source and still need to switch before edits,
   run `switch_start_branch_script --kind <kind>` serially. Your working branch
   remains `source_branch` after the switch.
   For an elite/final-donor continuation route, do not treat an `evolved_*`
   branch mentioned as fallback evidence as the parent. Keep the pre-seeded or
   materialized elite source unless Teacher's primary route explicitly assigns
   an evolved start branch.
6. Edit only files under `private_dpl_evolve_source`.
7. Before each canonical evaluation after a substantial mechanism change,
   create a local commit or record the current commit hash. This gives you a
   cheap source checkpoint if the next revision is worse.
8. Before final answer, make the source tree match the best clean canonical
   evaluation from this task. If a later revision worsened HPWL, restore the
   best clean commit before running `commit_source_script`.
   If the worsened revision was an active mechanism workbench with nonzero
   counters or useful stage-local gain, keep its commit hash and report it as a
   workbench checkpoint so Teacher can continue repairing it later.
9. Run `commit_source_script`.
10. Run `write_diff_script` after the final commit.

Generated workspace helpers that mutate the private source repo are serialized
by a file lock and must not be run in one parallel tool call:
`prepare_source_script`, `prepare_start_source_script`,
`switch_start_branch_script`, `build_variant_script`,
`evaluate_candidate_script`, `commit_source_script`, and `write_diff_script`.
Parallel file reads are fine after the source branch is prepared.

Run any manual `git diff --check` as `git -C "$private_dpl_evolve_source" diff
--check` or after `cd "$private_dpl_evolve_source"`. Generated build/evaluate
scripts may be launched from their script directory, but source git hygiene is
always scoped to the private source repo.

The orchestrator records the final commit after the Student exits.  If the
Student leaves uncommitted changes, the orchestrator may create a fallback
commit, but that is a safety net, not the intended workflow.

The final recorded commit, `implementation_diff`, metrics row, and knowledge
card must describe the same code state.  Do not report an earlier best run as
the final result while leaving a later, worse source revision checked out.

## Report

Report:

- source branch,
- final commit hash,
- active mechanism workbench commit hash if the final source restored a better
  donor,
- dirty status after commit,
- implementation diff path,
- any reason the Student could not commit.

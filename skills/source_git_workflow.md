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

## Required Flow

1. Open the workspace packet.
2. Run `prepare_source_script` to create or reuse the local source repo.
3. Confirm the generated script reports the expected branch and prepared
   `start/...` branches.
4. If Teacher assigns a specific prepared start point, run
   `switch_start_branch_script --kind <kind>` before edits. Your working branch
   remains `source_branch` after the switch.
   For an elite/final-donor continuation route, do not treat an `evolved_*`
   branch mentioned as fallback evidence as the parent. Keep the pre-seeded or
   materialized elite source unless Teacher's primary route explicitly assigns
   an evolved start branch.
5. Edit only files under `private_dpl_evolve_source`.
6. Before each canonical evaluation after a substantial mechanism change,
   create a local commit or record the current commit hash. This gives you a
   cheap source checkpoint if the next revision is worse.
7. Before final answer, make the source tree match the best clean canonical
   evaluation from this task. If a later revision worsened HPWL, restore the
   best clean commit before running `commit_source_script`.
8. Run `commit_source_script`.
9. Run `write_diff_script` after the final commit.

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
- dirty status after commit,
- implementation diff path,
- any reason the Student could not commit.

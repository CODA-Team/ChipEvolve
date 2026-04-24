# dpl_evolve_agent

`dpl_evolve_agent` is a standalone control repo for evolving
`tools/OpenROAD/src/dpl_evolve` without forking or modifying a large ORFS tree
more than necessary.

The short version:

- ORFS stays external.
- This repo stores prompts, scripts, patches, skills, and evaluator glue.
- Runtime state goes outside both repos.
- OpenROAD common code is built once.
- Each experiment variant rebuilds only its own `dpl_evolve` code and relinks a
  private `openroad` binary.

## Basic Layout

Recommended sibling layout:

```text
work/
  OpenROAD-flow-scripts/
  dpl_evolve_agent/
  dpl_evolve_state/
```

Required environment:

```bash
export DPL_EVOLVE_AGENT_ROOT=/abs/path/to/dpl_evolve_agent
export ORFS_ROOT=/abs/path/to/OpenROAD-flow-scripts
export DPL_EVOLVE_STATE_ROOT=/abs/path/to/dpl_evolve_state
```

If you prefer a local convenience link:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/attach_orfs_workspace.sh" \
  --workspace-root "$ORFS_ROOT"
```

That creates `$DPL_EVOLVE_AGENT_ROOT/.mounted_orfs`, which is ignored by git.

## Prepare ORFS

Prepare applies the small ORFS/OpenROAD overlay needed by this project:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/prepare_workspace.sh" \
  --workspace-root "$ORFS_ROOT"
```

This should not turn ORFS into the control repo. The agent remains standalone.

If you made a local ORFS clone and its relative OpenROAD submodule URL points
at a missing sibling path, set a local override for prepare:

```bash
export DPL_EVOLVE_OPENROAD_URL=https://github.com/The-OpenROAD-Project/OpenROAD.git
```

## Prepare Place Snapshots

The strict evaluator reuses an existing placement snapshot:

```text
flow/results/<platform>/<design>/<FLOW_VARIANT>/3_4_place_resized.odb
```

Create snapshots with:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/run_place_batch.sh"
```

If snapshots already exist, you can reuse their `FLOW_VARIANT`.

## Build Fast

Build common OpenROAD core once:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" 8
```

Create one private variant source and binary:

```bash
mkdir -p "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent"
rsync -a --delete \
  "$ORFS_ROOT/tools/OpenROAD/src/dpl_evolve/" \
  "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/dpl_evolve/"

"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent" \
  --dpl-src "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/dpl_evolve"

source "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/variant_env.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh" --threads 8
```

The variant build produces:

```text
${OPENROAD_BINARY}
${OPENROAD_INSTALL_ROOT}/bin/sta
```

`sta` is symlinked from the common-core build when available.

## Run One Evaluation

Use an explicit binary for variant runs:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/evaluator.py" \
  --problem "$DPL_EVOLVE_AGENT_ROOT/problems/gcd_nangate45/problem.yaml" \
  --mode single \
  --line evolve_line \
  --flow-variant <FLOW_VARIANT_WITH_3_4_PLACE_RESIZED_ODB> \
  --run-tag smoke_gcd \
  --skip-build \
  --openroad-binary "${OPENROAD_BINARY}" \
  --out "${DPL_EVOLVE_STATE_ROOT}/checkpoints/operations/smoke_gcd/eval.json"
```

Read:

```text
flow/reports/<platform>/<design>/<FLOW_VARIANT>/dpl_evolve_baseline/<run_tag>/metrics.json
```

## Run The Automated Codex Loop

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/run_design_evolve_loop.py" \
  --problem "$DPL_EVOLVE_AGENT_ROOT/problems/gcd_nangate45/problem.yaml" \
  --max-attempts 3
```

The loop handles checkpoint restore, packet refresh, Codex invocation, build,
evaluation, scoring, and accept/reject.

The Codex-facing contract is in:

```text
AGENTS.md
```

## Basic Principles

- Keep `dpl` upstream-clean.
- Evolve only `dpl_evolve`.
- Keep this repo standalone.
- Keep ORFS edits minimal and patch-based.
- Use common-core plus variant relink for fast parallel experiments.
- Always bind explicit `openroad` binaries for variant/family runs.

# dpl_evolve_agent

This README is for humans: setup, quick start, and the basic project model.
The Codex/agent execution contract lives in `AGENTS.md`.

`dpl_evolve_agent` is a standalone control repo for evolving
`tools/OpenROAD/src/dpl_evolve` without forking or modifying a large ORFS tree
more than necessary.

The short version:

- ORFS stays external.
- This repo stores prompts, scripts, patches, skills, and evaluator glue.
- Runtime state defaults to this repo's ignored `.dpl_evolve_state/`.
- The evolved command entrypoint is always `detailed_placement_evolve`.
- The current algorithm direction is a constrained top-level framework whose
  stages can be replaced by agents, not an unconstrained family-tree router.
- OpenROAD common code is built once.
- Each experiment variant rebuilds only its own `dpl_evolve` code and relinks a
  private `openroad` binary.

## Basic Layout

Recommended sibling layout:

```text
work/
  OpenROAD-flow-scripts/
  dpl_evolve_agent/
    .dpl_evolve_state/   # ignored runtime state
```

Recommended local setup:

```bash
cp env.sh.example env.sh
$EDITOR env.sh
source env.sh
```

`env.sh` is ignored by git. Keep machine-specific paths there, not in tracked
scripts or docs. The default `DPL_EVOLVE_STATE_ROOT` is
`$DPL_EVOLVE_AGENT_ROOT/.dpl_evolve_state`; use another local path only if you
need a larger scratch filesystem.

Case facts have one source of truth:

```text
problems/<case>/problem.yaml
```

Batch scripts may use named lists from `problems/case_sets.json`, but those
lists contain only case ids. They do not duplicate design configs or platform
facts.

If you prefer a local convenience link:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/attach_orfs_workspace.sh" \
  --workspace-root "$ORFS_ROOT"
```

That creates `$DPL_EVOLVE_AGENT_ROOT/.mounted_orfs`, which is ignored by git.

## Prepare ORFS

Prepare applies the small ORFS/OpenROAD overlay needed by this project,
including the clean `dpl_evolve` source and the constrained framework patch:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/prepare_workspace.sh" \
  --workspace-root "$ORFS_ROOT"
```

This should not turn ORFS into the control repo. The agent remains standalone.

If you made a local ORFS clone and its relative OpenROAD submodule URL points
at a missing sibling path, set a local override in `env.sh`:

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
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" 10
```

The reusable common core is stored under the agent state root, for example:

```text
dpl_evolve_agent/.dpl_evolve_state/openroad_core/<prepared-openroad-sha>/
```

The upstream OpenROAD anchor itself does not contain `src/dpl_evolve`; run the
prepare step first so the OpenROAD submodule is at the local prepared commit.

Create one private variant source and binary:

```bash
mkdir -p "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent"
rsync -a --delete \
  "$ORFS_ROOT/tools/OpenROAD/src/dpl_evolve/" \
  "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/dpl_evolve/"

"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent" \
  --dpl-src "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/dpl_evolve"

"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent" \
  --dpl-src "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/dpl_evolve" \
  --threads 10
```

The variant build produces:

```text
${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/install/OpenROAD/bin/openroad
${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/install/OpenROAD/bin/sta
```

`sta` is symlinked from the common-core build when available.

## Run One Evaluation

Use an explicit binary for variant runs:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/evaluator.py" \
  --case gcd_nangate45 \
  --mode single \
  --line evolve_default \
  --flow-variant <FLOW_VARIANT_WITH_3_4_PLACE_RESIZED_ODB> \
  --run-tag smoke_gcd \
  --skip-build \
  --openroad-binary "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/install/OpenROAD/bin/openroad" \
  --out "${DPL_EVOLVE_STATE_ROOT}/checkpoints/operations/smoke_gcd/eval.json"
```

Read:

```text
flow/reports/<platform>/<design>/<FLOW_VARIANT>/dpl_evolve_baseline/<run_tag>/metrics.json
```

## Source References

Future agents should learn from compact reference implementations instead of
wandering through historical experiments:

```text
family_variants/reference_sources/
```

That directory keeps the high-value donors:

- OpenROAD diamond DPL,
- OpenROAD negotiation / NBLG,
- LEGALM staged legalization,
- DREAMPlace Abacus.

Older family variants remain as archived evidence, but the default development
path is now:

```text
detailed_placement_evolve
  -> EvolveLegalizer top-level framework
  -> agent-modified stage implementation
  -> strict evaluator
  -> database evidence commit
```

## Run The Automated Codex Loop

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/run_design_evolve_loop.py" \
  --case gcd_nangate45 \
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

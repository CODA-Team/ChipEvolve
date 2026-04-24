# Standalone Agent Root Plus Common-Core Relink

This note defines the target architecture for `dpl_evolve_agent`.

The two main goals are:

- `dpl_evolve_agent` should be usable as a standalone control repo and should
  not conceptually depend on being registered as an ORFS git submodule
- after the first heavy bootstrap, each agent should only rebuild its own
  `dpl_evolve` code and then relink a private `openroad` binary

We do not need a runtime plugin system. A compile-time variant relink model is
enough.

## Design rules

1. `dpl_evolve_agent` is a standalone repo.
2. ORFS and OpenROAD remain the runtime/tool repos.
3. `dpl` stays upstream and does not host our new algorithm path.
4. `dpl_evolve` is the only variant-owned compile surface.
5. Every family or agent run binds an explicit binary path.
6. Common OpenROAD libraries should be built once and reused across variants.

## What should no longer be required

The target architecture should **not** require:

- `dpl_evolve_agent` to be committed inside ORFS
- `dpl_evolve_agent` to be mounted specifically at `ORFS_ROOT/evolve_agent`
- one shared `tools/OpenROAD/build`
- one shared `tools/install/OpenROAD`
- every variant to rerun a full OpenROAD build graph

The only intended runtime contract is:

- `DPL_EVOLVE_AGENT_ROOT`
- `ORFS_ROOT`
- `DPL_EVOLVE_STATE_ROOT`

An ignored local mount at `DPL_EVOLVE_AGENT_ROOT/.mounted_orfs` is allowed only
as a convenience for setting `ORFS_ROOT`.

## Runtime roots

The target runtime should revolve around three explicit roots:

- `ORFS_ROOT`
  The OpenROAD-flow-scripts workspace used to run the flow.
- `DPL_EVOLVE_AGENT_ROOT`
  The standalone control repo root.
- `DPL_EVOLVE_STATE_ROOT`
  External mutable state: prepared patches, core build cache, variant source
  trees, variant build/install roots, loop records, and logs.

If `ORFS_ROOT` contains spaces, build scripts create a stable symlink under
`DPL_EVOLVE_STATE_ROOT` and use that path for CMake configure/build. The stable
alias is runtime state because CMake records source paths in
`compile_commands.json` and link recipes.

Once the scripts are refactored, the runtime should not care whether
`DPL_EVOLVE_AGENT_ROOT` lives inside ORFS, beside ORFS, or somewhere else.

## Recommended directory layout

```text
<workspace_parent>/
  OpenROAD-flow-scripts/
    flow/
    tools/OpenROAD/

  dpl_evolve_agent/
    scripts/
    baseline/
    skills/
    knowledge/
    family_variants/

  dpl_evolve_state/
    anchors/
    openroad_core/
      <anchor_id>/
        build/
        install/OpenROAD/
        exports/
    variants/
      <agent_or_family_id>/
        dpl_evolve/
        build/
        install/OpenROAD/
        variant_env.sh
        logs/
    operations/
      <loop_id>/
```

Interpretation:

- ORFS is the runtime flow/artifact workspace
- `dpl_evolve_agent` is the control plane repo
- `dpl_evolve_state` is the mutable runtime cache

This layout keeps source, artifacts, and per-agent binaries cleanly separated.

## Build layers

### Layer A: prepared OpenROAD source

Prepare once per anchor pair:

- patch ORFS only where strictly needed
- patch OpenROAD to inject clean `src/dpl_evolve`
- keep classic `dpl` untouched

This is still the job of:

- `prepare_workspace.sh`
- `patches/openroad_dpl_evolve_base.patch`
- `patches/orfs_make_overlay.patch`

### Layer B: common core

Build once per `(OpenROAD anchor, toolchain, CMake options)` combination.

This layer contains:

- common OpenROAD libraries
- common Tcl registration infrastructure outside variant-owned code
- common third-party link products already provided by the environment

Target output:

```text
${DPL_EVOLVE_STATE_ROOT}/openroad_core/<anchor_id>/
  build/
  install/OpenROAD/
  exports/
```

This layer should be immutable during a batch of experiments.

### Layer C: variant-owned `dpl_evolve`

Each agent or family owns:

- one materialized `dpl_evolve` source tree
- one private build root
- one private install root
- one private `openroad` binary

Target output:

```text
${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>/
  dpl_evolve/
  build/
  install/OpenROAD/
  variant_env.sh
```

### Layer D: final relink

Each variant performs only:

- compile variant `dpl_evolve_lib`
- compile variant `dpl_evolve`
- relink final `openroad`
- link the common-core `sta` binary into the variant install tree when it is
  available

Everything else should come from the immutable common core layer.

## Why the current codebase is close

The current OpenROAD tree already has the right starting points:

- `src/CMakeLists.txt` already supports `DPL_EVOLVE_SRC_DIR`
- `dpl_evolve` is already its own CMake target pair:
  - `dpl_evolve_lib`
  - `dpl_evolve`
- `openroad` already links `dpl_evolve`

So we do **not** need a plugin architecture first.

What is still missing is exporting/reusing the common OpenROAD targets cleanly
instead of rebuilding them in every variant build directory.

## Implementation direction

### Phase 1: decouple the control repo from ORFS path assumptions

Refactor scripts so they resolve runtime paths from:

- `ORFS_ROOT`
- `DPL_EVOLVE_AGENT_ROOT`
- `DPL_EVOLVE_STATE_ROOT`

instead of assuming:

- `repo_root/evolve_agent`

Expected script changes:

- `repo_root()` and `resolve_workspace_root()` helpers stop requiring a mounted
  `evolve_agent/`
- checkpoint/packet paths move under `DPL_EVOLVE_STATE_ROOT/operations`
- knowledge/tasks/skills are loaded from `DPL_EVOLVE_AGENT_ROOT`

### Phase 2: introduce a common-core bootstrap

Add explicit core scripts:

- `configure_openroad_core.sh`
- `build_openroad_core.sh`

Inputs:

- `ORFS_ROOT/tools/OpenROAD`
- anchor metadata
- toolchain environment
- core build/install root

Outputs:

- immutable common core build tree
- immutable common core install tree
- exported CMake target metadata

### Phase 3: add variant relink configure/build

Add explicit variant scripts:

- `configure_openroad_variant_relink.sh`
- `build_openroad_variant_relink.sh`

Inputs:

- `--core-root`
- `--variant-root`
- `--dpl-src`

Outputs:

- variant-local `dpl_evolve` build products
- variant-local relinked `openroad`
- variant env file that pins:
  - `OPENROAD_BUILD_DIR`
  - `OPENROAD_INSTALL_ROOT`
  - `OPENROAD_BINARY`
  - `DPL_EVOLVE_SRC_DIR`

Current implementation status:

- `configure_openroad_core.sh`
- `build_openroad_core.sh`
- `configure_openroad_variant_relink.sh`
- `build_openroad_variant_relink.sh`

support the preferred common-core plus lightweight relink workflow.

The relink path does not copy a full OpenROAD build tree and does not rerun
CMake for each variant. It reads the common-core compile/link recipes, rebuilds
only the variant-owned `dpl_evolve` objects, relinks a private `openroad`, and
symlinks the common-core `sta` into the variant install directory.

A two-case smoke on `2026-04-24` validated that AES and IBEX can evaluate in
parallel with different private `openroad` binaries from the same common core.

The next real reduction step is:

- stop treating the copied full build tree as the reusable unit
- instead export or preserve only the truly common targets
- keep variant reconfigure narrow enough that only `dpl_evolve` and the final
  `openroad` relink become dirty

### Phase 4: switch loops and evaluators to explicit binaries

At that point:

- baseline/evolve wrappers should take explicit `--openroad-binary`
- family runs should always reject implicit root-binary use
- multi-agent loops can run in parallel as long as each one has its own
  variant root and binary

## Target script surface

The intended long-term entrypoints are:

- `prepare_workspace.sh`
- `configure_openroad_core.sh`
- `build_openroad_core.sh`
- `materialize_family_variant.sh`
- `configure_openroad_variant_relink.sh`
- `build_openroad_variant_relink.sh`
- `run_canonical_line.sh`
- `run_design_evolve_loop.py`

The current `build_openroad_only.sh` can remain as the transitional build
wrapper until the core/relink split becomes real.

## Binary policy

Binary selection must stay explicit.

- clean baseline and clean evolve runs may use a designated root/core binary
- family or agent variants must use their own binary
- loops should record the exact binary path in evaluator output and operation
  metadata

The preferred run shape is:

```bash
source "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>/variant_env.sh"

./scripts/run_canonical_line.sh \
  --line evolve_line \
  --openroad-binary "${OPENROAD_BINARY}" \
  ...
```

## Concurrency model

The target architecture should support:

- one shared prepared ORFS/OpenROAD source anchor
- one shared common core per anchor
- many parallel variant binaries
- many parallel case runs

It should **not** require:

- one shared mutable build tree
- one shared mutable install tree
- one shared binary for all agents

## Why this is enough

This model gives us the practical wins we actually need:

- `dpl_evolve_agent` can live outside ORFS
- each agent can keep private local source edits
- the first heavy build happens once
- later variant work is much lighter
- every run still executes a normal standalone `openroad` binary

That is the right middle ground for this project.

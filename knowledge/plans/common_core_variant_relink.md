# Common Core Plus Variant Relink

This note describes the medium-term build model for `dpl_evolve_agent`.

The goal is not a runtime plugin system. The goal is a practical workflow where:

- the heavy bootstrap happens once
- each agent keeps its own local `dpl_evolve` source tree
- each variant rebuild is lighter than a full OpenROAD rebuild
- each variant still produces its own standalone `openroad` binary

## Current stable model

Today the stable workflow is:

1. prepare a clean ORFS/OpenROAD workspace
2. keep `tools/OpenROAD/src/dpl_evolve` as the clean evolve base
3. materialize a family variant into its own source tree
4. configure a dedicated variant build/install root
5. build OpenROAD only in that build root
6. run the desired line with an explicit variant binary

This gives us:

- per-agent source isolation
- per-agent build isolation
- per-agent install isolation
- per-agent binary isolation

It does not yet give true cross-variant reuse of already-linked common libs.

## Binary policy

Binary selection must stay explicit.

- clean baseline and clean evolve runs may use the root binary
- family-variant runs must use a variant binary
- the preferred pattern is:
  - `configure_openroad_variant.sh`
  - `source <variant-root>/variant_env.sh`
  - `build_openroad_only.sh`
  - `run_canonical_line.sh --openroad-binary "${OPENROAD_BINARY}" ...`

The wrappers should reject family-variant runs that do not bind an explicit
binary.

## Medium-term target

The medium-term model is:

1. build the OpenROAD common core once
2. keep that common core immutable for the duration of a batch
3. let each variant compile only its own `dpl_evolve` code
4. relink a thin final `openroad` binary per variant

That is enough for our current scale. We do not need runtime-loaded plugins.

## Proposed build layers

### Layer A: common core

This layer contains everything that does not depend on the local
`dpl_evolve` source tree.

Examples:

- `ord`
- shared OpenROAD tool libraries
- Tcl registration infrastructure outside `dpl_evolve`
- third-party dependencies already bootstrapped on the machine

Desired properties:

- built once per anchor/toolchain combination
- stored under a shared cache root
- reused by many variants without recompiling

Suggested location:

```text
.codex_state/openroad_core/<anchor_id>/
  build/
  install/OpenROAD/
```

### Layer B: variant-local `dpl_evolve`

This layer is agent-owned.

Each agent keeps:

- its own materialized `dpl_evolve` source tree
- its own build dir
- its own install root
- its own final binary

Suggested location:

```text
.codex_state/family_variants/<family_or_agent>/dpl_evolve
.codex_state/openroad_variants/<agent_id>/
  build/
  install/OpenROAD/
  variant_env.sh
```

### Layer C: final relink

After the variant-local `dpl_evolve` objects are built, the final step should
be a thin relink of `openroad`.

The intended rebuild surface is:

- `dpl_evolve_lib`
- `dpl_evolve`
- final `openroad` link

The heavy common libraries should come from Layer A rather than being rebuilt
per variant.

## Required CMake direction

To get there cleanly, the build graph needs to distinguish between:

- common OpenROAD libraries
- variant-owned `dpl_evolve` libraries
- final `openroad` link target

The important architectural point is:

- `dpl_evolve` remains a compile-time component
- but it becomes the only variant-owned compile surface

We do not need to redesign the runtime command surface or add plugin loading.

## Script evolution

### What we already have

- `materialize_family_variant.sh`
- `configure_openroad_variant.sh`
- `build_openroad_only.sh`

### What the medium-term scripts should grow toward

#### Shared core bootstrap

One script or mode should prepare the shared core once:

```text
configure_openroad_core.sh
build_openroad_core.sh
```

or equivalent modes folded into the existing scripts.

Inputs:

- upstream OpenROAD anchor
- toolchain / module environment
- common install root

Outputs:

- shared core build tree
- shared core install root

#### Variant configure

`configure_openroad_variant.sh` should eventually accept a shared core root and
bind the local `dpl_evolve` tree against it.

Suggested future parameters:

- `--core-root`
- `--variant-root`
- `--dpl-src`

#### Variant build

`build_openroad_only.sh` should keep its current OpenROAD-only behavior, but
gain a mode that explicitly means:

- reuse shared core artifacts
- rebuild variant-owned `dpl_evolve`
- relink `openroad`

## Why this is enough

This model already solves the practical bottlenecks we care about:

- agents can keep private local source trees
- agents can run in parallel with separate binaries
- the first heavy compile happens once
- later variant work is much lighter

It avoids the complexity of:

- runtime plugin loading
- ABI management across dynamically loaded legalizers
- fragile symbol/export contracts for Tcl registration

## Agent-facing rules

Agent docs should continue to enforce:

- patch `tools/OpenROAD/src/dpl_evolve/` for clean-base work
- patch materialized variant trees for family work
- source the variant env file before building/running a family variant
- pass `--openroad-binary "${OPENROAD_BINARY}"` on family runs
- never assume the root binary is correct inside a family loop

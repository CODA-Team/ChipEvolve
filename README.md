# dpl_evolve_agent

`dpl_evolve_agent` is the standalone control plane for `dpl_evolve`.

The runtime model is one explicit scheme:

- `ORFS_ROOT`: the OpenROAD-flow-scripts workspace
- `DPL_EVOLVE_AGENT_ROOT`: this standalone control repo
- `DPL_EVOLVE_STATE_ROOT`: external packet/checkpoint/operation state

`dpl_evolve_agent` is not defined by being a git submodule inside ORFS.
Scripts operate through the roots above.

An ignored local mount is supported only as a convenience:

- `DPL_EVOLVE_AGENT_ROOT/.mounted_orfs`

If you want that convenience mount, use:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/attach_orfs_workspace.sh" \
  --workspace-root /abs/path/to/OpenROAD-flow-scripts
```

The design note is:

- `$DPL_EVOLVE_AGENT_ROOT/knowledge/plans/common_core_variant_relink.md`

For the current script entrypoints and the explicit list of generated runtime
paths to ignore, start with:

- `$DPL_EVOLVE_AGENT_ROOT/SCRIPT_MAP.md`

For directory-specific summaries, also see:

- `$DPL_EVOLVE_AGENT_ROOT/scripts/README.md`
- `$DPL_EVOLVE_AGENT_ROOT/skills/README.md`
- `$DPL_EVOLVE_AGENT_ROOT/configs/README.md`
- `$DPL_EVOLVE_AGENT_ROOT/problems/README.md`
- `$DPL_EVOLVE_AGENT_ROOT/tasks/README.md`
- `$DPL_EVOLVE_AGENT_ROOT/EXAMPLE.md`

Its job is deliberately narrow:

- define the problem we are solving
- compile a small context packet for Codex
- call the existing build and baseline entrypoints
- read `metrics.json`
- record local checkpoints for edit-state switching

It should stay decoupled from the OpenROAD implementation. The legalizer code
lives in `tools/OpenROAD/src/dpl_evolve/`. The control plane should never grow
into a second copy of the target plane.

The clean initial evolve base is:

- `tools/OpenROAD/src/dpl_evolve/`

Family-specific legalizers or initializers belong in:

- `$DPL_EVOLVE_AGENT_ROOT/family_variants/`

They are materialized into dedicated source trees and built into dedicated
OpenROAD binaries. They are not reintroduced into the clean main-tree base.

The medium-term build direction is:

- build the OpenROAD common core once
- let each agent keep a private `dpl_evolve` tree
- compile only variant-owned `dpl_evolve`
- relink a private `openroad` binary per agent
- symlink common-core `sta` into each variant install tree when needed

The runtime-facing script sequence for that model is:

- `$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh`
- `$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh`
- `$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh`
- `source <variant-root>/variant_env.sh`
- `$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh`

When `ORFS_ROOT` contains spaces, build scripts use a stable symlink under
`DPL_EVOLVE_STATE_ROOT` for CMake. This keeps `compile_commands.json` and relink
recipes reusable across runs.

The strict baseline wrapper also uses the stable ORFS alias for `make run` and
reuses an existing `3_4_place_resized.odb` snapshot instead of rebuilding
upstream placement stages.

The older full-variant OpenROAD configure path still exists as a fallback:

- `$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant.sh`
- `source <variant-root>/variant_env.sh`
- `$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_only.sh`

The project-level run concepts are intentionally small:

- canonical baseline lines
- the clean evolve line
- family variants
- strict legalization-only comparison
- a small ORFS overlay patch set plus one OpenROAD clean-`dpl_evolve` patch

Internal dispatcher details are not the main workflow vocabulary.

## Before code evolve

Before running any design-specific code evolve loop, prepare initial place
snapshots first. The evolve prompts assume a reusable `3_4_place_resized.odb`
already exists for the target design.

Use:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/run_place_batch.sh"
```

This batch launcher is the control-plane copy of the place preparation flow.
It runs the design set from `flow/run_place_batch.sh` and writes the usual ORFS
artifacts under `flow/results`, `flow/reports`, `flow/logs`, and `flow/objects`.

Skipping this step usually wastes time later, because Codex will reach the
evolve stage without a valid placement snapshot to reuse.

## Automated design evolve loop

If you want a single Python entrypoint that repeatedly calls Codex, evaluates
the current patch on one design, and keeps only accepted improvements, use:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/run_design_evolve_loop.py" \
  --problem "$DPL_EVOLVE_AGENT_ROOT/problems/gcd_nangate45/problem.yaml" \
  --max-attempts 3
```

The loop does three important things automatically:

- it creates and restores local checkpoints between attempts
- it calls the existing evaluator and judges the patch on HPWL, runtime,
  memory, WNS, and TNS
- it writes a persistent local memory for the loop under
  `${DPL_EVOLVE_STATE_ROOT}/checkpoints/operations/<loop_id>/`

The loop memory is kept in:

- `experience_journal.md`
- `experience_log.jsonl`

Each new Codex attempt receives a compact excerpt from that journal, so the
agent does not have to start blind on every round.

## Four planes

- `tools/OpenROAD/src/dpl_evolve/`: target plane
  C++ / Tcl legalizer implementation and tests.
- `flow/`: artifact plane
  ORFS outputs under `results/`, `reports/`, `logs/`, and `objects/`.
- `dpl_evolve_agent/`: control plane
  problem definitions, skills, knowledge packets, and evaluator wrappers.
- optional upstream scheduler/runtime references:
  not required in-tree; if checked out later, keep them outside the target plane
  and use them only as runtime-toolbox references.

## Minimal execution loop

The loop we want is intentionally small:

1. Create or refresh a local baseline checkpoint with
   `scripts/checkpoint.py`.
2. Pick a problem in `problems/`.
3. Run `adapters/science_codeevolve/kb_query.py` to build a compact packet.
4. Let Codex patch only the allowed target-plane files.
5. Build through `scripts/build_openroad_core.sh` once, then use
   `scripts/build_openroad_variant_relink.sh` for private variant binaries.
   Use `scripts/build_openroad_only.sh` only for the clean root binary or as a
   fallback full-variant build path. The first OpenROAD-only configure disables
   OpenROAD tests by default and publishes only the needed binaries unless
   `OPENROAD_INSTALL_MODE=cmake` is set.
6. Run one canonical baseline/evolve line or the full suite through the existing
   baseline scripts.
7. Read `flow/reports/.../metrics.json`.
8. Capture a new checkpoint or restore an older one.

## After a baseline run

Do not pick the first patch family from memory alone. Once the base line has
finished, classify the case from its canonical `metrics.json` first:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/recommend_initial_family.py" \
  --metrics flow/reports/<platform>/<design>/<flow_variant>/dpl_evolve_baseline/<run_tag>/metrics.json
```

That recommendation is intentionally narrow:

- it identifies the case regime from real baseline metrics
- it points at the current reusable initial family paths
- it helps choose whether to start from a `legalm_engine` variant, the
  runtime-aware negotiation base, or the priority-escape stack

The long-lived rules behind that selector live in:

- `$DPL_EVOLVE_AGENT_ROOT/knowledge/family_components/initial_patch_paths.yaml`
- `$DPL_EVOLVE_AGENT_ROOT/knowledge/replay_bank/family_registry.yaml`

## Stable interfaces

The control plane should rely on only two stable interfaces:

### 1. Runner interface

These scripts are the canonical execution surface:

- `$DPL_EVOLVE_AGENT_ROOT/scripts/run_canonical_line.sh`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/run_baseline_suite.sh`

The control plane should call them. `baseline/run_baseline.sh` still exists,
but it is the internal dispatcher behind these entrypoints. The control plane
should not reimplement legalization flows or metrics collection.

### 2. Result interface

This file is the canonical evaluator surface:

- `flow/reports/<platform>/<design>/<flow_variant>/dpl_evolve_baseline/<run_tag>/metrics.json`

If deeper debugging is needed, follow `supporting_files` inside `metrics.json`
to the raw JSON and report files.

## Multi-variant OpenROAD builds

If different agents need different `dpl_evolve` implementations, do not force
them to share one `tools/OpenROAD/build` or one `tools/install/OpenROAD`.

Use a dedicated variant root per agent instead:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/materialize_family_variant.sh" \
  --family legalm_engine \
  --output-dir "${DPL_EVOLVE_STATE_ROOT}/family_variants/legalm_engine/dpl_evolve" \
  --force

"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" 8

"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/agent_a" \
  --dpl-src "${DPL_EVOLVE_STATE_ROOT}/family_variants/legalm_engine/dpl_evolve"

source "${DPL_EVOLVE_STATE_ROOT}/variants/agent_a/variant_env.sh"

"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh" --threads 8
```

Binary-selection rules:

- clean `evolve_line` may use the root OpenROAD binary
- any `--family-variant` run must use an explicit variant binary
- the safest pattern is:
  - source `variant_env.sh`
  - still pass `--openroad-binary "${OPENROAD_BINARY}"` on family runs

Then point evaluation at that binary with either:

- `BUDGET_CONFIG.openroad_build_dir`
- `BUDGET_CONFIG.openroad_install_root`
- `BUDGET_CONFIG.openroad_binary`

or the matching evaluator CLI flags.

The important idea is:

- each agent gets its own `build`
- each agent gets its own `install`
- each agent gets its own `openroad` binary
- case-level isolation still comes from `flow_variant` and `run_tag`

The current preferred build path is a shared common-core build plus
per-variant `dpl_evolve` compilation and a thin final relink. The design note
is:

- `$DPL_EVOLVE_AGENT_ROOT/knowledge/plans/common_core_variant_relink.md`

The older full-variant OpenROAD configure path is still available as a
fallback when relink is insufficient.

## Canonical lines

The canonical line list lives in:

- `$DPL_EVOLVE_AGENT_ROOT/baseline/canonical_lines.yaml`

That file is the shortest statement of:

- what counts as a baseline line
- what counts as the clean evolve line
- how a family variant plugs into the same evolve line

## Directory map

- `skills/`
  Short operational instructions for Codex.
- `knowledge/`
  Compiled and queryable project knowledge, not raw paper dumps.
- `problems/`
  Design-specific task definitions.
- `configs/`
  Run configuration presets.
- `adapters/science_codeevolve/`
  Thin wrappers for packet generation, evaluation, archiving, and local runtime
  guards such as directory locks and timeout-protected subprocess execution.
- `scripts/`
  Small convenience entrypoints for bootstrapping, Codex execution, or running loops.
- `family_variants/`
  Materialized-family manifests and patch assets for source-tree variants.
- `tasks/`
  Human-authored task sheets for bounded Codex work.
- `checkpoints/`
  Local-only checkpoint store. This is intentionally ignored by git.
  Checkpoint metadata lives here, and `scripts/checkpoint.py` keeps a
  restorable snapshot for each operation.

## Keep it simple

To keep the system clear and decoupled:

- put algorithm code only in the target plane
- put run outputs only in the artifact plane
- let the control plane orchestrate, not reimplement
- let Codex read packets, not whole repo dumps
- use one evaluator path based on `metrics.json`
- use git anchors plus local snapshots for restorable checkpoints

## Checkpoint model

`checkpoints/` is local-only and ignored. It exists to make a stateless agent
behave predictably:

- git provides the provenance anchor:
  root branch / commit and OpenROAD branch / commit
- `scripts/checkpoint.py` provides the local restore path:
  it captures `DPL_EVOLVE_AGENT_ROOT/` and `tools/OpenROAD/src/dpl_evolve/`
- a reviewer can inspect one operation directory and see:
  what changed, what was run, what came back, and how to restore that state

The practical rule is:

- baseline identity comes from git
- fast edit-state switching comes from the checkpoint script
- run artifacts still live under `flow/`

## Codex invocation logging

If you want to run `codex exec` from inside this control plane and keep a local
record of the invocation itself, use:

- `$DPL_EVOLVE_AGENT_ROOT/scripts/run_codex_exec.py`

It writes a local operation directory under `${DPL_EVOLVE_STATE_ROOT}/checkpoints/operations/`
with:

- copied prompt text
- raw JSONL event stream from `codex exec --json`
- stderr log
- last message
- token usage summary
- optional cost estimate when explicit pricing is supplied

## Runtime policy

`dpl_evolve_agent` is intentionally conservative about algorithm behavior and more
aggressive about runtime hygiene.

Good places to be aggressive:

- directory locking
- timeout and memory guards
- process cleanup
- compact telemetry and failure tails
- thin orchestration helpers

Places to stay conservative:

- target-plane patch scope
- target-plane default behavior
- importing external evolution cores

That is why `adapters/science_codeevolve/` only borrows the runtime-toolbox
layer from the upstream project, not its population/evolution machinery.

## Recommended read order

1. `$DPL_EVOLVE_AGENT_ROOT/AGENTS.md`
2. `$DPL_EVOLVE_AGENT_ROOT/SCRIPT_MAP.md`
3. `$DPL_EVOLVE_AGENT_ROOT/skills/README.md`
4. `$DPL_EVOLVE_AGENT_ROOT/knowledge/plans/common_core_variant_relink.md`

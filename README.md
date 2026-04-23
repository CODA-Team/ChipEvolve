# evolve_agent

`evolve_agent` is the control plane for `dpl_evolve`.

For the current script entrypoints and the explicit list of generated script
paths to ignore, start with:

- `evolve_agent/SCRIPT_MAP.md`

For directory-specific summaries, also see:

- `evolve_agent/scripts/README.md`
- `evolve_agent/configs/README.md`
- `evolve_agent/problems/README.md`
- `evolve_agent/tasks/README.md`
- `evolve_agent/EXAMPLE.md`

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

- `evolve_agent/family_variants/`

They are materialized into dedicated source trees and built into dedicated
OpenROAD binaries. They are not reintroduced into the clean main-tree base.

The project-level run concepts are intentionally small:

- canonical baseline lines
- the clean evolve line
- family variants
- strict legalization-only comparison

Internal dispatcher details are not the main workflow vocabulary.

## Before code evolve

Before running any design-specific code evolve loop, prepare initial place
snapshots first. The evolve prompts assume a reusable `3_4_place_resized.odb`
already exists for the target design.

Use:

```bash
./evolve_agent/scripts/run_place_batch.sh
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
python3 evolve_agent/scripts/run_design_evolve_loop.py \
  --problem evolve_agent/problems/gcd_nangate45/problem.yaml \
  --max-attempts 3
```

The loop does three important things automatically:

- it creates and restores local checkpoints between attempts
- it calls the existing evaluator and judges the patch on HPWL, runtime,
  memory, WNS, and TNS
- it writes a persistent local memory for the loop under
  `evolve_agent/checkpoints/operations/<loop_id>/`

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
- `evolve_agent/`: control plane
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
5. Build with the existing ORFS/OpenROAD build path.
6. Run one canonical baseline/evolve line or the full suite through the existing
   baseline scripts.
7. Read `flow/reports/.../metrics.json`.
8. Capture a new checkpoint or restore an older one.

## After a baseline run

Do not pick the first patch family from memory alone. Once the base line has
finished, classify the case from its canonical `metrics.json` first:

```bash
python3 evolve_agent/scripts/recommend_initial_family.py \
  --metrics flow/reports/<platform>/<design>/<flow_variant>/dpl_evolve_baseline/<run_tag>/metrics.json
```

That recommendation is intentionally narrow:

- it identifies the case regime from real baseline metrics
- it points at the current reusable initial family paths
- it helps choose whether to start from a `legalm_engine` variant, the
  runtime-aware negotiation base, or the priority-escape stack

The long-lived rules behind that selector live in:

- `evolve_agent/knowledge/family_components/initial_patch_paths.yaml`
- `evolve_agent/knowledge/replay_bank/family_registry.yaml`

## Stable interfaces

The control plane should rely on only two stable interfaces:

### 1. Runner interface

These scripts are the canonical execution surface:

- `evolve_agent/scripts/run_canonical_line.sh`
- `evolve_agent/baseline/run_baseline_suite.sh`

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
./evolve_agent/scripts/materialize_family_variant.sh \
  --family legalm_engine \
  --output-dir ./.codex_state/family_variants/legalm_engine/dpl_evolve \
  --force

./evolve_agent/scripts/configure_openroad_variant.sh \
  --variant-root ./.codex_state/openroad_variants/agent_a \
  --dpl-src ./.codex_state/family_variants/legalm_engine/dpl_evolve

OPENROAD_BUILD_DIR=./.codex_state/openroad_variants/agent_a/build \
OPENROAD_INSTALL_ROOT=./.codex_state/openroad_variants/agent_a/install/OpenROAD \
OPENROAD_BINARY=./.codex_state/openroad_variants/agent_a/install/OpenROAD/bin/openroad \
./evolve_agent/scripts/build_openroad_only.sh 8
```

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

## Canonical lines

The canonical line list lives in:

- `evolve_agent/baseline/canonical_lines.yaml`

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
  it captures `evolve_agent/` and `tools/OpenROAD/src/dpl_evolve/`
- a reviewer can inspect one operation directory and see:
  what changed, what was run, what came back, and how to restore that state

The practical rule is:

- baseline identity comes from git
- fast edit-state switching comes from the checkpoint script
- run artifacts still live under `flow/`

## Codex invocation logging

If you want to run `codex exec` from inside this control plane and keep a local
record of the invocation itself, use:

- `evolve_agent/scripts/run_codex_exec.py`

It writes a local operation directory under `evolve_agent/checkpoints/operations/`
with:

- copied prompt text
- raw JSONL event stream from `codex exec --json`
- stderr log
- last message
- token usage summary
- optional cost estimate when explicit pricing is supplied

## Runtime policy

`evolve_agent` is intentionally conservative about algorithm behavior and more
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

1. `evolve_agent/AGENTS.md`
2. `knowledge/stage_context/detail_place_stack.yaml`
3. `knowledge/delta_ledger/nblg_to_openroad.yaml`
4. `tasks/archive/CODEX_SETUP_REPO_AND_VERIFY.md`

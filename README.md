# dpl_evolve_agent

`dpl_evolve_agent` is the control repo for case-specific detailed-placement
algorithm evolution on top of an external OpenROAD-flow-scripts workspace.

This README is intentionally short. It is for humans who need to set up the
repo and run the top-level workflow. Agent execution contracts, generated
packets, variant relink details, and prompt rules live in the linked docs below.

## What This Repo Does

- Keeps ORFS external and mostly clean.
- Applies a small `dpl_evolve` overlay to OpenROAD.
- Runs strict baseline/evolve comparisons from existing placement snapshots.
- Orchestrates Teacher/Student Codex loops that edit private `dpl_evolve`
  variants and judge them with independent metrics.

The evolved OpenROAD command stays:

```text
detailed_placement_evolve
```

The strict comparison anchor is the normal OpenROAD detailed-placement flow:

```text
detailed_placement -> improve_placement -> optimize_mirroring
```

## Required Layout

Recommended sibling layout:

```text
work/
  OpenROAD-flow-scripts/
  dpl_evolve_agent/
```

Runtime state is ignored by git and normally lives here:

```text
dpl_evolve_agent/.dpl_evolve_state/
```

## Environment

Create a local env file:

```bash
cp env.sh.example env.sh
$EDITOR env.sh
source env.sh
```

Required variables:

```bash
export DPL_EVOLVE_AGENT_ROOT="/abs/path/to/dpl_evolve_agent"
export ORFS_ROOT="/abs/path/to/OpenROAD-flow-scripts"
export DPL_EVOLVE_STATE_ROOT="${DPL_EVOLVE_AGENT_ROOT}/.dpl_evolve_state"
```

Keep machine-local paths in ignored `env.sh`, not in tracked files.

## Runtime Dependencies

You need:

- `bash`, `git`, `python3`, `make`, `cmake`, and a working C++ toolchain.
- OpenROAD/ORFS build dependencies already available on the machine.
- Python with `yaml`/PyYAML for evaluator and case-registry paths.
- `codex` CLI

If the default Python cannot import `yaml`, set candidates in `env.sh`:

```bash
export DPL_EVOLVE_PYTHON_CANDIDATES="/path/to/python3:/another/python"
```

## Prepare Workspace

Prepare ORFS/OpenROAD once before launched experiments:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/prepare_workspace.sh" \
  --workspace-root "$ORFS_ROOT"
```

This applies the supported local overlay and refreshes seed sources used by the
Teacher/Student loop. ORFS remains the external workspace; this repo remains
the control repo.

## Prepare Input Snapshots

The evaluator expects an existing placement snapshot:

```text
flow/results/<platform>/<design>/<FLOW_VARIANT>/3_4_place_resized.odb
```

Create or refresh snapshots with:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/run_place_batch.sh"
```

If a snapshot already exists, reuse its `FLOW_VARIANT`.

## Run Baselines

Run the canonical baseline suite for a case:

```bash
"$DPL_EVOLVE_AGENT_ROOT/baseline/run_baseline_suite.sh" \
  --case jpeg_nangate45 \
  --flow-variant <FLOW_VARIANT_WITH_3_4_PLACE_RESIZED_ODB> \
  --threads 10 \
  --tag-prefix baseline_probe
```

Read results under:

```text
$ORFS_ROOT/flow/reports/<platform>/<design>/<FLOW_VARIANT>/dpl_evolve_baseline/<run_tag>/metrics.json
```

## Run The Teacher/Student Loop

Generate a reviewable round without calling Codex:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case jpeg_nangate45 \
  --flow-variant <FLOW_VARIANT_WITH_3_4_PLACE_RESIZED_ODB> \
  --start-kind framework \
  --children 4 \
  --iterations 2 \
  --dry-run \
  --audit-prompts
```

Launch a real round:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case jpeg_nangate45 \
  --flow-variant <FLOW_VARIANT_WITH_3_4_PLACE_RESIZED_ODB> \
  --prepare-workspace \
  --start-kind framework \
  --children 4 \
  --iterations 3 \
  --max-parallel 2 \
  --launch
```

Each launched round refreshes the canonical baseline suite first, then runs:

```text
Teacher plan -> Student implementation/eval -> Teacher review -> next iteration
```

Round outputs live under:

```text
$DPL_EVOLVE_STATE_ROOT/teacher_rounds/<round_id>/
```

Useful files:

```text
round.log
events.jsonl
iter_XX/context/iteration_context.md
iter_XX/prompts/
iter_XX/packet/
students/student_XX/iter_XX/artifacts/
```

## Watch A Round

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/watch_teacher_round.py" \
  <round_id> \
  --watch
```

Or serve a local dashboard:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/watch_teacher_round.py" \
  <round_id> \
  --serve --host 127.0.0.1 --port 8765
```

## Where Details Live

- `AGENTS.md`: coding-agent contract and algorithm constraints.
- `scripts/README.md`: script inventory, common-core build, variant relink,
  generated packets, and Teacher/Student mechanics.
- `prompt_templates/teacher_loop/README.md`: prompt template rules.
- `problems/README.md`: case registry format.
- `knowledge/EVIDENCE_POLICY.md`: how to classify observations, hypotheses,
  and durable evidence.
- `family_variants/REFERENCE_INDEX.yaml`: compact source-code donor index.

## Repo Hygiene

Before sharing the repo or asking an agent to consume it:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/audit_repo_hygiene.py"
git diff --check
```

Tracked files should not contain machine-local paths, runtime state, build
products, or stale family-tree workflow instructions.

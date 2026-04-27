# dpl_evolve_agent

## Introduction

`dpl_evolve_agent` is the control repo for case-specific detailed-placement
algorithm evolution on top of an external OpenROAD-flow-scripts workspace.

It does four things:

- Applies a small `dpl_evolve` overlay to OpenROAD/ORFS.
- Keeps algorithm edits isolated in private per-student `dpl_evolve` variants.
- Runs strict baseline/evolve evaluations from existing placement snapshots.
- Orchestrates Teacher/Student Codex loops that review code, metrics, and logs
  across multiple iterations.

The evolved OpenROAD command stays:

```text
detailed_placement_evolve
```

The strict comparison anchor is the normal OpenROAD detailed-placement flow:

```text
detailed_placement -> improve_placement -> optimize_mirroring
```

## Install Dependencies

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

Create a machine-local environment file:

```bash
cd /path/to/dpl_evolve_agent
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

You need:

- `bash`, `git`, `python3`, `make`, `cmake`, and a working C++ toolchain.
- OpenROAD/ORFS build dependencies already available on the machine.
- Python with `yaml`/PyYAML for evaluator and case-registry paths.
- `codex` CLI for launched Teacher/Student runs.

If the default Python cannot import `yaml`, set candidates in `env.sh`:

```bash
export DPL_EVOLVE_PYTHON_CANDIDATES="/path/to/python3:/another/python"
```

Most examples assume you run from the parent workspace:

```bash
cd "$(dirname "$DPL_EVOLVE_AGENT_ROOT")"
source "$DPL_EVOLVE_AGENT_ROOT/env.sh"
```

## Quick Run

This is the copy/paste flow for "repatch ORFS/OpenROAD into the framework
state, compile the common core, then run `ibex_nangate45`".

Reset to the supported anchors and apply the framework overlay:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/prepare_workspace.sh" \
  --workspace-root "$ORFS_ROOT" \
  --force
```

`--force` resets the ORFS/OpenROAD workspaces to the recorded anchors before
patching. Use it only when it is safe to discard local ORFS/OpenROAD edits.

Build the reusable OpenROAD core once:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh"

"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" \
  --threads 10
```

Confirm the framework seed exists:

```bash
test -f "$DPL_EVOLVE_STATE_ROOT/seed_sources/framework_dpl_evolve/src/EvolveLegalizer.cpp" && \
test -f "$DPL_EVOLVE_STATE_ROOT/seed_sources/framework_dpl_evolve/src/DifferentialGuidance.cpp" && \
echo "framework seed ready"
```

Launch the ibex Teacher/Student loop:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case ibex_nangate45 \
  --flow-variant place_batch_20260421_220319 \
  --round-id ibex_framework_2x2_$(date +%Y%m%d_%H%M%S) \
  --start-kind framework \
  --children 2 \
  --iterations 2 \
  --max-parallel 2 \
  --teacher-model gpt-5.5 \
  --teacher-reasoning-effort high \
  --student-model gpt-5.4 \
  --student-reasoning-effort high \
  --launch
```

The script prints the round directory. It also follows this pattern:

```text
$DPL_EVOLVE_STATE_ROOT/teacher_rounds/<round_id>/
```

Watch a launched round:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/watch_teacher_round.py" \
  <round_id> \
  --watch
```

Serve a local dashboard:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/watch_teacher_round.py" \
  <round_id> \
  --serve --host 127.0.0.1 --port 8765
```

## Technical Details

### Workspace Prepare

Prepare ORFS/OpenROAD once before launched experiments:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/prepare_workspace.sh" \
  --workspace-root "$ORFS_ROOT"
```

This applies the supported local overlay and refreshes seed sources used by the
Teacher/Student loop. ORFS remains the external workspace; this repo remains
the control repo.

After prepare, the common OpenROAD core should be built by the top-level flow:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" --threads 10
```

Student variants only relink private `dpl_evolve` sources against this core;
they should not rebuild the common OpenROAD core themselves.

### Input Snapshots

The evaluator expects an existing placement snapshot:

```text
flow/results/<platform>/<design>/<FLOW_VARIANT>/3_4_place_resized.odb
```

Create or refresh snapshots with:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/run_place_batch.sh"
```

If a snapshot already exists, reuse its `FLOW_VARIANT`.

### Baselines

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

### Teacher/Student Loop

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
  --round-id jpeg_test_2x2 \
  --start-kind framework \
  --children 2 \
  --iterations 2 \
  --max-parallel 2 \
  --teacher-model gpt-5.5 \
  --teacher-reasoning-effort high \
  --student-model gpt-5.4 \
  --student-reasoning-effort high \
  --launch
```

If you want the top-level command to also run `prepare_workspace.sh` first, add
`--prepare-workspace`. For day-to-day experiments, it is usually clearer to run
the prepare/build commands explicitly once, then launch rounds without
`--prepare-workspace`.

Each launched round refreshes the canonical baseline suite first, then runs:

```text
Teacher plan -> Student implementation/eval -> Teacher review -> next iteration
```

Teacher/Student Codex sessions run with their cwd set to the parent workspace
by default. The orchestrator explicitly grants them access to:

```text
$DPL_EVOLVE_AGENT_ROOT
$ORFS_ROOT
$DPL_EVOLVE_STATE_ROOT
```

Follow-up prompts are compact by default after iteration 1, and each student
keeps one stable active workspace across iterations. The orchestrator snapshots
every iteration for review and rollback.

### Round Outputs

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

Each student's stable active workspace is:

```text
$DPL_EVOLVE_STATE_ROOT/teacher_rounds/<round_id>/students/student_XX/workspace/
```

The editable private source tree is:

```text
$DPL_EVOLVE_STATE_ROOT/teacher_rounds/<round_id>/students/student_XX/workspace/variant/dpl_evolve
```

After every launched iteration, the orchestrator snapshots that source to:

```text
$DPL_EVOLVE_STATE_ROOT/teacher_rounds/<round_id>/students/student_XX/source_backups/iter_XX/dpl_evolve
```

Per-iteration build/eval logs and diffs stay in:

```text
$DPL_EVOLVE_STATE_ROOT/teacher_rounds/<round_id>/students/student_XX/iter_XX/artifacts/
```

### Model Flags

Model and reasoning flags can be set globally or split by role:

```text
--model <model> --reasoning-effort <low|medium|high|xhigh>
--teacher-model <model> --teacher-reasoning-effort <low|medium|high|xhigh>
--student-model <model> --student-reasoning-effort <low|medium|high|xhigh>
```

`--max-parallel` controls how many Student workers run at the same time.
Teacher plan and Teacher review stay sequential; this setting is mainly a
resource limit for parallel Student implementation/evaluation.

### Start Kinds

`--start-kind` chooses the initial private source seed for each student:

```text
framework  constrained top-level dpl_evolve framework; normal default
diamond    direct/default DPL-style evolve seed; useful as a contrast line
prepared   copy the current ORFS dpl_evolve source; useful for local debug only
```

### Where More Details Live

- `AGENTS.md`: coding-agent contract and algorithm constraints.
- `scripts/README.md`: script inventory, common-core build, variant relink,
  generated packets, and Teacher/Student mechanics.
- `prompt_templates/teacher_loop/README.md`: prompt template rules.
- `problems/README.md`: case registry format.
- `knowledge/EVIDENCE_POLICY.md`: how to classify observations, hypotheses,
  and durable evidence.
- `family_variants/REFERENCE_INDEX.yaml`: compact source-code donor index.

### Repo Hygiene

Before sharing the repo or asking an agent to consume it:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/audit_repo_hygiene.py"
git diff --check
```

Tracked files should not contain machine-local paths, runtime state, build
products, or stale family-tree workflow instructions.

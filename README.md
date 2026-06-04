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

Tracked scripts and docs should refer to directory prefixes through
`DPL_EVOLVE_AGENT_ROOT`, `ORFS_ROOT`, and `DPL_EVOLVE_STATE_ROOT`; local
absolute paths belong only in ignored `env.sh` or the shell environment.

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
  <this repo>/
```

Runtime state is ignored by git and normally lives here:

```text
$DPL_EVOLVE_AGENT_ROOT/.dpl_evolve_state/
```

You need:

- `bash`, `git`, `python3`, `make`, `cmake`, and a working C++ toolchain.
- OpenROAD/ORFS build dependencies already available on the machine.
- Python with `yaml`/PyYAML for evaluator and case-registry paths.
- `codex` CLI for launched Teacher/Student runs.

## Experiment Runbook

Use this section as the end-to-end operator flow for preparing the workspace,
running a smoke experiment, and then scaling to larger case batches. Commands
assume the sibling layout from `Install Dependencies`.

### 0. Configure Runtime Roots

Create a machine-local `env.sh` and source it before every run:

```bash
cd /path/to/dpl_evolve_agent
cp env.sh.example env.sh
$EDITOR env.sh
source env.sh
```

At minimum:

```bash
export DPL_EVOLVE_AGENT_ROOT="/abs/path/to/dpl_evolve_agent"
export ORFS_ROOT="/abs/path/to/OpenROAD-flow-scripts"
export DPL_EVOLVE_STATE_ROOT="${DPL_EVOLVE_AGENT_ROOT}/.dpl_evolve_state"
```

For large or repeated campaigns, `DPL_EVOLVE_STATE_ROOT` may point outside the
repo, for example to a scratch filesystem. Tracked scripts and generated
packets should use these variables instead of local absolute paths.

If the default `python3` cannot import `yaml`, set:

```bash
export DPL_EVOLVE_PYTHON_CANDIDATES="/usr/bin/python3:/path/to/another/python3"
```

### 1. Run The Repo Gate

Before touching ORFS/OpenROAD, run the static release-readiness gate:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/repo/check_release_readiness.sh"
```

This checks Python compile, shell syntax, knowledge index validity, repo
hygiene, prompt generation, and generated Student helper-script syntax.

When ORFS/OpenROAD is unavailable but you still want the static checks:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/repo/check_release_readiness.sh" \
  --skip-teacher-dry-run
```

### 2. Prepare ORFS And Seed Sources

Prepare the external ORFS/OpenROAD workspace once before real experiments:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/prepare_workspace.sh" \
  --workspace-root "$ORFS_ROOT"
```

Use `--force` only when it is safe to reset ORFS/OpenROAD branches to the
recorded anchors:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/prepare_workspace.sh" \
  --workspace-root "$ORFS_ROOT" \
  --force
```

This applies the supported overlay and refreshes prepared start-kind seed
sources under:

```text
$DPL_EVOLVE_STATE_ROOT/seed_sources/
```

The active starts are:

```text
framework
diamond
default_negotiation
```

### 3. Build The Common OpenROAD Core

Build the shared OpenROAD core once. Student variants later relink only their
private `dpl_evolve` source against this core.

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/configure_openroad_core.sh"

"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/build_openroad_core.sh" \
  --threads 10
```

If the core is already built and you are only launching another round, pass
`--skip-core-build` to `optimize_case_with_codex.py`.

### 4. Create Or Reuse Placement Snapshots

Every experiment needs an input placement snapshot:

```text
$ORFS_ROOT/flow/results/<platform>/<design>/<FLOW_VARIANT>/3_4_place_resized.odb
```

To create one snapshot for a smoke case:

```bash
export FLOW_VARIANT="smoke_snapshot_$(date +%Y%m%d_%H%M%S)"

"$DPL_EVOLVE_AGENT_ROOT/scripts/evaluator/run_place_batch.sh" \
  --case jpeg_nangate45 \
  --max-tasks 1 \
  --num-cores 8 \
  --flow-variant "$FLOW_VARIANT"
```

To create snapshots for the default place-batch case set:

```bash
export FLOW_VARIANT="place_batch_$(date +%Y%m%d_%H%M%S)"

"$DPL_EVOLVE_AGENT_ROOT/scripts/evaluator/run_place_batch.sh" \
  --case-set place_batch \
  --max-tasks 5 \
  --num-cores 8 \
  --flow-variant "$FLOW_VARIANT"
```

If a snapshot already exists, reuse its `FLOW_VARIANT`.

### 5. Run Baselines

Run the canonical strict baseline suite before interpreting evolved candidates:

```bash
"$DPL_EVOLVE_AGENT_ROOT/baseline/run_baseline_suite.sh" \
  --case jpeg_nangate45 \
  --flow-variant "$FLOW_VARIANT" \
  --threads 10 \
  --tag-prefix jpeg_smoke_baseline
```

Baseline reports live under:

```text
$ORFS_ROOT/flow/reports/<platform>/<design>/<FLOW_VARIANT>/dpl_evolve_baseline/
```

The headline metric is `metrics.json:hpwl`.

### 6. Dry-Run The Teacher/Student Prompts

Before launching Codex workers, generate prompts and helper scripts without
running agents:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case jpeg_nangate45 \
  --flow-variant "$FLOW_VARIANT" \
  --round-id dryrun_jpeg_$(date +%Y%m%d_%H%M%S) \
  --start-kind framework \
  --iterations 1 \
  --children 2 \
  --max-parallel 2 \
  --skip-baseline-preflight \
  --skip-core-build \
  --dry-run \
  --audit-prompts
```

Use the generated `PROMPT_AUDIT.md` to confirm agent prompts stay compact and
the generated Student helper scripts point at the expected role-namespaced
scripts.

### 7. Run A One-Case 1T2S Smoke

After prepare, core build, and snapshot are ready, run one real Teacher plus
two Students.  A launched smoke must refresh the three canonical baselines
(`openroad_dpl_flow`, `openroad_dpl_negotiation`, and `evolve_default`) before
the Teacher sees candidate evidence:

```bash
export ROUND_ID="smoke_1t2s_$(date +%Y%m%d_%H%M%S)"

python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case jpeg_nangate45 \
  --flow-variant "$FLOW_VARIANT" \
  --round-id "$ROUND_ID" \
  --start-kind framework \
  --iterations 1 \
  --children 2 \
  --max-parallel 2 \
  --threads 8 \
  --student-runtime-multiplier 1.0 \
  --teacher-reasoning-effort low \
  --student-reasoning-effort low \
  --skip-core-build \
  --audit-prompts \
  --launch
```

This smoke checks the complete chain:

```text
Teacher plan -> two parallel Students -> private relink/eval -> artifact gate -> Teacher review
```

Watch it in a terminal:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/orchestration/watch_teacher_round.py" \
  "$ROUND_ID" \
  --watch
```

Or serve the local dashboard:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/orchestration/watch_teacher_round.py" \
  "$ROUND_ID" \
  --serve --host 127.0.0.1 --port 8765
```

### 8. Run A Normal Case Experiment

For a normal case-specific search, increase iterations and keep baseline
preflight enabled unless the baseline was just refreshed:

```bash
export ROUND_ID="jpeg_framework_4x2_$(date +%Y%m%d_%H%M%S)"

python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case jpeg_nangate45 \
  --flow-variant "$FLOW_VARIANT" \
  --round-id "$ROUND_ID" \
  --start-kind framework \
  --iterations 2 \
  --children 4 \
  --max-parallel 2 \
  --threads 10 \
  --teacher-reasoning-effort high \
  --student-reasoning-effort high \
  --skip-core-build \
  --audit-prompts \
  --launch
```

Optional target-local start probe before Teacher planning:

```bash
  --calibrate-start-seeds
```

That probe evaluates `framework`, `diamond`, and `default_negotiation` on the
target case and writes a `start_seed_calibration.md` packet for Teacher.

### 9. Inspect Results

Round state lives under:

```text
$DPL_EVOLVE_STATE_ROOT/<round_id>/teacher_rounds/
```

Useful files:

```text
round.log
PROMPT_AUDIT.md
iter_XX/context/iteration_context.md
iter_XX/prompts/
iter_XX/packet/
students/student_XX/iter_XX/artifacts/candidate_metrics_summary.md
students/student_XX/iter_XX/artifacts/implementation.diff
students/student_XX/iter_XX/artifacts/knowledge_card.md
```

Each Student's private source tree is:

```text
$DPL_EVOLVE_STATE_ROOT/<round_id>/teacher_rounds/students/student_XX/workspace/variant/dpl_evolve
```

### 10. Validate Candidate Transfer

After a promising round, run fixed-source matrix validation:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/matrix/run_round_candidate_matrices.sh" \
  --round-id "$ROUND_ID" \
  --plan "$DPL_EVOLVE_AGENT_ROOT/configs/experiment_plans/flow_knowledge_core_util.tsv" \
  --threads 10 \
  --matrix-row-parallel 1 \
  --skip-baseline-matrix
```

Matrix outputs live under:

```text
$DPL_EVOLVE_STATE_ROOT/<round_id>/candidate_matrix_batches/
```

## Quick Run

This is the copy/paste flow for "repatch ORFS/OpenROAD into the framework
state, compile the common core, then run one case from an existing placement
snapshot".

Create and source the machine-local environment:

```bash
cd /path/to/dpl_evolve_agent
cp env.sh.example env.sh
$EDITOR env.sh
source env.sh
```

At minimum, `env.sh` should define:

```bash
export DPL_EVOLVE_AGENT_ROOT="/abs/path/to/dpl_evolve_agent"
export ORFS_ROOT="/abs/path/to/OpenROAD-flow-scripts"
export DPL_EVOLVE_STATE_ROOT="${DPL_EVOLVE_AGENT_ROOT}/.dpl_evolve_state"
```

Keep machine-local paths in ignored `env.sh`, not in tracked files.

If the default Python cannot import `yaml`, set candidates in `env.sh`:

```bash
export DPL_EVOLVE_PYTHON_CANDIDATES="/path/to/python3:/another/python"
```

Run from the parent workspace that contains both repos:

```bash
cd "$(dirname "$DPL_EVOLVE_AGENT_ROOT")"
source "$DPL_EVOLVE_AGENT_ROOT/env.sh"
```

Before launching expensive ORFS/OpenROAD work, run the repo-level static gate:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/repo/check_release_readiness.sh"
```

Use `--skip-teacher-dry-run` only when the local ORFS/OpenROAD roots are not
available and you only need compile, shell, knowledge, and repo-hygiene checks.

Reset to the supported anchors and apply the framework overlay:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/prepare_workspace.sh" \
  --workspace-root "$ORFS_ROOT" \
  --force
```

`--force` resets the ORFS/OpenROAD workspaces to the recorded anchors before
patching. Use it only when it is safe to discard local ORFS/OpenROAD edits.

Build the reusable OpenROAD core once:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/configure_openroad_core.sh"

"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/build_openroad_core.sh" \
  --threads 10
```

Confirm the framework seed exists:

```bash
test -f "$DPL_EVOLVE_STATE_ROOT/seed_sources/framework_dpl_evolve/src/EvolveLegalizer.cpp" && \
test -f "$DPL_EVOLVE_STATE_ROOT/seed_sources/framework_dpl_evolve/src/LegalmGuidance.cpp" && \
echo "framework seed ready"
```

Choose an existing snapshot variant. It must contain:

```text
$ORFS_ROOT/flow/results/<platform>/<design>/<FLOW_VARIANT>/3_4_place_resized.odb
```

If you need to create snapshots first, use `scripts/evaluator/run_place_batch.sh`.

```bash
export FLOW_VARIANT="<FLOW_VARIANT_WITH_3_4_PLACE_RESIZED_ODB>"
```

Run the case baseline first:

```bash
"$DPL_EVOLVE_AGENT_ROOT/baseline/run_baseline_suite.sh" \
  --case ibex_nangate45 \
  --flow-variant "$FLOW_VARIANT" \
  --threads 10 \
  --tag-prefix ibex_framework_baseline
```

The launch step also refreshes the canonical baseline suite, but running it
explicitly first gives you a visible anchor before Teacher/Student evolution
starts.

Launch the ibex Teacher/Student loop:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case ibex_nangate45 \
  --flow-variant "$FLOW_VARIANT" \
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
$DPL_EVOLVE_STATE_ROOT/<round_id>/teacher_rounds/
```

Watch a launched round:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/orchestration/watch_teacher_round.py" \
  <round_id> \
  --watch
```

Serve a local dashboard:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/orchestration/watch_teacher_round.py" \
  <round_id> \
  --serve --host 127.0.0.1 --port 8765
```

## Technical Details

### Workspace Prepare

Prepare ORFS/OpenROAD once before launched experiments:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/prepare_workspace.sh" \
  --workspace-root "$ORFS_ROOT"
```

This applies the supported local overlay and refreshes seed sources used by the
Teacher/Student loop. ORFS remains the external workspace; this repo remains
the control repo.

After prepare, the common OpenROAD core should be built by the top-level flow:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/configure_openroad_core.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/build_openroad_core.sh" --threads 10
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
"$DPL_EVOLVE_AGENT_ROOT/scripts/evaluator/run_place_batch.sh"
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

The canonical HPWL field is `metrics.json:hpwl`, sourced from OpenROAD/DPL
pin-based log lines such as `[INFO DPL-0022] HPWL after`.  The legacy
cell-bbox `hpwl_proxy` may still appear for debugging; do not use it for
promotion, Teacher decisions, or published tables.

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
every iteration for review, matrix testing, and lineage comparison.

### Round Outputs

Round outputs live under:

```text
$DPL_EVOLVE_STATE_ROOT/<round_id>/teacher_rounds/
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
$DPL_EVOLVE_STATE_ROOT/<round_id>/teacher_rounds/students/student_XX/workspace/
```

The editable private source tree is:

```text
$DPL_EVOLVE_STATE_ROOT/<round_id>/teacher_rounds/students/student_XX/workspace/variant/dpl_evolve
```

The editable private source tree is a local git repository. Each student should
commit its final source state on the fixed per-iteration branch, and the
orchestrator creates a fallback commit only if the student leaves source
changes uncommitted. The committed revision is recorded at:

```text
$DPL_EVOLVE_STATE_ROOT/<round_id>/teacher_rounds/students/student_XX/iter_XX/artifacts/source_commit.json
```

Per-iteration build/eval logs and diffs stay in:

```text
$DPL_EVOLVE_STATE_ROOT/<round_id>/teacher_rounds/students/student_XX/iter_XX/artifacts/
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
framework             constrained top-level dpl_evolve framework with LEGALM-style producer/frontier and bounded DPO handoff support
diamond               direct/default DPL-style evolve seed; useful as a contrast line
default_negotiation   framework-compatible source layout with negotiation enabled by default
```

`framework` is the CLI default. These starts are source basins for the first
private workspace, not edit-scope restrictions or universal answers. Teacher
may keep, switch, or repair the source basin based on the current case metrics,
logs, peer evidence, and source diagnosis.

Prepared starts are materialized by `scripts/workspace/prepare_workspace.sh` into
generated workspaces. Patch catalogs under `patches/evolved_legalizers/` are
release/reproduction evidence used by maintenance scripts; they are not manual
Student commands and should not be applied directly inside a Student private
source tree.

Before a new case-specific round, `--calibrate-start-seeds` can compile and
run the prepared start-kind seed branches on the target case.  This is a
target-local start-kind probe, not paper-level Level 1 calibration.  The
generated `start_seed_calibration.md` packet gives Teacher initial stage-wise
evidence for `framework`, `diamond`, and `default_negotiation` before Student
routes are assigned.

### Where More Details Live

- `docs/REPO_REDESIGN_BLUEPRINT.md`: repo redesign plan and migration phases.
- `docs/RUNTIME_CONTRACT.md`: runtime roots, protected evaluator, and generated state.
- `docs/KNOWLEDGE_CONTRACT.md`: default/on-demand/reference knowledge rules.
- `calibration/README.md`: ReviewDSE Level 1 calibration contract.
- `AGENTS.md`: coding-agent contract and algorithm constraints.
- `scripts/README.md`: script inventory, common-core build, variant relink,
  generated packets, and Teacher/Student mechanics.
- `prompt_templates/teacher_loop/README.md`: prompt template rules.
- `problems/README.md`: case registry format.
- `knowledge/policies/evidence_policy.md`: how to classify observations, hypotheses,
  and durable evidence.
- `knowledge/index/` plus `scripts/repo/query_knowledge.py`: concise stage skill and blueprint-stack lookup.
- `knowledge/support/dpo/source_level_mechanisms.md`: improve-placement mechanism lessons.
- `family_variants/REFERENCE_INDEX.yaml`: compact source-code donor index.

### Repo Hygiene

Before sharing the repo or asking an agent to consume it:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/repo/check_release_readiness.sh" --skip-teacher-dry-run
git diff --check
```

Tracked files should not contain machine-local paths, runtime state, build
products, or stale family-tree workflow instructions.

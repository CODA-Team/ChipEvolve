# dpl_evolve_agent

`dpl_evolve_agent` is the control repo for evolving OpenROAD detailed-placement
algorithms on one placement case at a time.

The repo does not replace OpenROAD-flow-scripts.  It prepares an external,
clean `OpenROAD-flow-scripts` workspace, builds a shared OpenROAD core, gives
each Student agent a private `dpl_evolve` source tree, evaluates candidates
against strict baselines, and keeps all generated runtime state outside tracked
source files.

## What You Need

- A Linux shell with `bash`, `git`, `python3`, `cmake`, `make`, and a C++
  compiler.
- A clean `OpenROAD-flow-scripts` checkout.
- OpenROAD/ORFS build dependencies installed on the machine.
- Python with PyYAML available to the selected interpreter.
- The `codex` CLI configured for launched Teacher/Student runs.

Recommended layout:

```text
work/
  OpenROAD-flow-scripts/
  dpl_evolve_agent/
```

All commands below assume this repo is `dpl_evolve_agent`.

## 1. Configure Runtime Paths

Create a local `env.sh`:

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

`env.sh` is ignored by git.  Keep machine-local paths there, not in tracked
files.

If the default Python cannot import `yaml`, add:

```bash
export DPL_EVOLVE_PYTHON_CANDIDATES="/usr/bin/python3:/path/to/another/python3"
```

If a clean ORFS clone has a local OpenROAD submodule URL problem, point prepare
at a valid OpenROAD source:

```bash
export DPL_EVOLVE_OPENROAD_URL="/abs/path/to/OpenROAD"
```

## 2. Check The Control Repo

Run the lightweight repo gate:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/repo/check_release_readiness.sh" \
  --skip-teacher-dry-run
```

When `ORFS_ROOT` is ready and you want prompt-generation checks too:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/repo/check_release_readiness.sh"
```

## 3. Prepare A Clean ORFS Workspace

Start from a clean `OpenROAD-flow-scripts` checkout.  If there are local ORFS or
OpenROAD edits you care about, save them before this step.

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/prepare_workspace.sh" \
  --workspace-root "$ORFS_ROOT" \
  --force
```

`--force` resets ORFS/OpenROAD to the supported anchors, applies the
`dpl_evolve` overlay, and refreshes prepared source starts under:

```text
$DPL_EVOLVE_STATE_ROOT/seed_sources/
```

The active start branches are:

```text
framework
diamond
default_negotiation
```

## 4. Build The Shared OpenROAD Core

Build once after prepare:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/configure_openroad_core.sh"

"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/build_openroad_core.sh" \
  --threads 10
```

Later Student variants relink only their private `dpl_evolve` sources against
this core.  For later launches, pass `--skip-core-build` if this core is still
valid.

Load the shared binary for ORFS snapshot/baseline commands:

```bash
CORE_ENV="$(find "$DPL_EVOLVE_STATE_ROOT/openroad_core" -mindepth 2 \
  -maxdepth 2 -name core_env.sh | sort | tail -n 1)"
source "$CORE_ENV"
export OPENROAD_EXE="$OPENROAD_BINARY"
```

## 5. Create A Placement Snapshot

Each case run needs:

```text
$ORFS_ROOT/flow/results/<platform>/<design>/<FLOW_VARIANT>/3_4_place_resized.odb
```

Create one snapshot for a single case:

```bash
export FLOW_VARIANT="snapshot_aes_$(date +%Y%m%d_%H%M%S)"

"$DPL_EVOLVE_AGENT_ROOT/scripts/evaluator/run_place_batch.sh" \
  --case aes_nangate45 \
  --max-tasks 1 \
  --num-cores 8 \
  --flow-variant "$FLOW_VARIANT"
```

If `make check-yosys` fails in a clean ORFS clone, point ORFS at an installed
Yosys:

```bash
export YOSYS_EXE="/abs/path/to/yosys"
```

If the snapshot already exists, just reuse its `FLOW_VARIANT`.

Useful built-in case ids live in `problems/`, for example:

```text
aes_nangate45
jpeg_nangate45
ibex_nangate45
gcd_nangate45
aes_asap7
jpeg_asap7
```

## 6. Optional: Run Mechanism Calibration

Calibration is optional.  Use it when you want Teacher to assign many distinct
single-mechanism probes before a normal evolve run.

Calibration is one iteration only.  Scale breadth with `--children`, not with
`--iterations`.

Small dry-run check:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case aes_nangate45 \
  --flow-variant "$FLOW_VARIANT" \
  --round-id calib_dryrun_aes_$(date +%Y%m%d_%H%M%S) \
  --iterations 1 \
  --children 5 \
  --max-parallel 2 \
  --calibration-mode \
  --skip-baseline-preflight \
  --skip-core-build \
  --dry-run \
  --audit-prompts
```

Full 50-child calibration pool:

```bash
export ROUND_ID="calib_aes_50x10_$(date +%Y%m%d_%H%M%S)"

python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case aes_nangate45 \
  --flow-variant "$FLOW_VARIANT" \
  --round-id "$ROUND_ID" \
  --start-kind framework \
  --iterations 1 \
  --children 50 \
  --max-parallel 10 \
  --threads 8 \
  --student-runtime-multiplier 1.0 \
  --calibration-mode \
  --calibrate-start-seeds \
  --skip-core-build \
  --audit-prompts \
  --launch
```

In calibration mode, Teacher is prompted to:

- assign one independent mechanism per Student;
- spread work across `framework`, `diamond`, and `default_negotiation`;
- spread mechanisms across legalizer, handoff/frontier, DPO, transaction,
  reorder/local DP, post-consumer preservation, and runtime-budget stages;
- avoid guard lanes;
- avoid mirror as the primary improvement path;
- review results as effective, repairable, or negative mechanism evidence.

Calibration artifacts stay under:

```text
$DPL_EVOLVE_STATE_ROOT/<round_id>/teacher_rounds/
```

The Teacher review and Student `knowledge_card.md` files are the source for
later human-reviewed knowledge updates.

## 7. Run A Single-Case Evolve Round

First generate prompts without launching agents:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case aes_nangate45 \
  --flow-variant "$FLOW_VARIANT" \
  --round-id evolve_dryrun_aes_$(date +%Y%m%d_%H%M%S) \
  --start-kind framework \
  --iterations 1 \
  --children 2 \
  --max-parallel 2 \
  --skip-baseline-preflight \
  --skip-core-build \
  --dry-run \
  --audit-prompts
```

Then launch a smoke run with one Teacher and two Students:

```bash
export ROUND_ID="smoke_aes_1t2s_$(date +%Y%m%d_%H%M%S)"

python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case aes_nangate45 \
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

Real launched rounds must keep baseline preflight enabled.  The launcher runs
the three canonical comparison lines before Teacher planning:

```text
openroad_dpl_flow
openroad_dpl_negotiation
evolve_default
```

For a larger single-case search:

```bash
export ROUND_ID="evolve_aes_4x2_$(date +%Y%m%d_%H%M%S)"

python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case aes_nangate45 \
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

## 8. Watch A Run

Terminal watcher:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/orchestration/watch_teacher_round.py" \
  "$ROUND_ID" \
  --watch
```

Local dashboard:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/orchestration/watch_teacher_round.py" \
  "$ROUND_ID" \
  --serve --host 127.0.0.1 --port 8765
```

Quick status report:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/analysis/report_experiment_status.py" \
  --round-id "$ROUND_ID" \
  --detail-round "$ROUND_ID" \
  --children 2
```

## 9. Read Results

Round state:

```text
$DPL_EVOLVE_STATE_ROOT/<round_id>/teacher_rounds/
```

Important files:

```text
round.log
events.jsonl
PROMPT_AUDIT.md
iter_01/context/iteration_context.md
iter_01/prompts/
iter_01/packet/
students/student_XX/iter_01/artifacts/candidate_metrics_summary.md
students/student_XX/iter_01/artifacts/implementation.diff
students/student_XX/iter_01/artifacts/knowledge_card.md
```

Student private source:

```text
$DPL_EVOLVE_STATE_ROOT/<round_id>/teacher_rounds/students/student_XX/workspace/variant/dpl_evolve
```

Baseline and candidate metrics:

```text
$ORFS_ROOT/flow/reports/<platform>/<design>/<FLOW_VARIANT>/dpl_evolve_baseline/
```

Use final `metrics.json:hpwl` for promotion decisions.  Legal-stage HPWL and
raw counters are diagnostic evidence, not the final ranking target.

## 10. Common Commands

Run only the canonical baselines:

```bash
"$DPL_EVOLVE_AGENT_ROOT/baseline/run_baseline_suite.sh" \
  --case aes_nangate45 \
  --flow-variant "$FLOW_VARIANT" \
  --threads 8 \
  --tag-prefix baseline_aes_$(date +%Y%m%d_%H%M%S)
```

Validate prompt generation for calibration at the full 50-child size without
launching agents:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case aes_nangate45 \
  --flow-variant "$FLOW_VARIANT" \
  --round-id calib_prompt_50_dryrun_$(date +%Y%m%d_%H%M%S) \
  --iterations 1 \
  --children 50 \
  --max-parallel 10 \
  --calibration-mode \
  --skip-baseline-preflight \
  --skip-core-build \
  --dry-run \
  --audit-prompts
```

Run repository checks before sharing changes:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/repo/check_release_readiness.sh" \
  --skip-teacher-dry-run

git diff --check
```

## More Documentation

- `scripts/README.md`: script inventory and lower-level mechanics.
- `docs/RUNTIME_CONTRACT.md`: runtime roots and generated state contract.
- `docs/KNOWLEDGE_CONTRACT.md`: knowledge loading and evidence rules.
- `calibration/README.md`: tracked calibration evidence contract.
- `prompt_templates/teacher_loop/README.md`: prompt-template maintenance rules.
- `problems/README.md`: case registry format.
- `knowledge/policies/evidence_policy.md`: how to classify evidence.

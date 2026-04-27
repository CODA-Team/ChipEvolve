# Scripts

This directory contains the active helper scripts for the constrained
`detailed_placement_evolve` framework.

Runtime roots:

- `DPL_EVOLVE_AGENT_ROOT`
- `ORFS_ROOT`
- `DPL_EVOLVE_STATE_ROOT`

## Script Inventory

Every active script is listed here.  If a file is not listed, it should not be
part of the default workflow.

### Workspace And Runtime

| Script | Purpose | Called by | Stage |
| --- | --- | --- | --- |
| `scripts/runtime_env.sh` | Resolve `DPL_EVOLVE_AGENT_ROOT`, `ORFS_ROOT`, `DPL_EVOLVE_STATE_ROOT`, and stable build aliases. | Sourced by shell entrypoints. | All shell-script stages. |
| `scripts/prepare_workspace.sh` | Prepare a clean ORFS/OpenROAD workspace by applying supported patches and snapshot reusable `dpl_evolve` seed sources. | Human/Teacher before experiments. | Bootstrap. |
| `scripts/case_registry.py` | Resolve cases from the single `problems/` registry. | `run_place_batch.sh`, `run_baseline.sh`, Teacher tooling, humans. | Case selection. |
| `scripts/checkpoint.py` | Snapshot/restore local candidate source state under ignored runtime state. | Teacher/child loop and manual recovery. | Experiment state management. |
| `scripts/audit_repo_hygiene.py` | Check that GitHub-facing files avoid stale family-flow references and unclassified patch artifacts. | Human/CI-style preflight. | Repo hygiene. |

### Build And Relink

| Script | Purpose | Called by | Stage |
| --- | --- | --- | --- |
| `scripts/configure_openroad_core.sh` | Write common-core `core_env.sh` with build/install/binary paths. | Human/Teacher before common-core build. | Common-core configure. |
| `scripts/build_openroad_core.sh` | Choose the common-core root and delegate the actual OpenROAD build. | Human/Teacher before variants. | Common-core build. |
| `scripts/build_openroad_only.sh` | Single OpenROAD configure/build/install implementation.  Also used by evaluator `openroad_only` mode. | `build_openroad_core.sh`, evaluator, advanced manual builds. | Common-core or explicit OpenROAD build. |
| `scripts/create_variant_start.sh` | Copy a `dpl_evolve` seed into one private variant source tree. `--start-kind framework` starts from the constrained top framework; `--start-kind diamond` starts from the direct DPL/evolve base; `--start-kind prepared` copies the current ORFS tree; `--seed-src` can start from an elite source backup. Preserves existing source unless `--force` is passed. | Human/Teacher/child agents. | Variant initialize. |
| `scripts/configure_openroad_variant_relink.sh` | Write `variant_env.sh` for a private candidate `dpl_evolve` source. | Human/Teacher/child agents. | Variant configure. |
| `scripts/build_openroad_variant_relink.sh` | Thin shell wrapper around the Python relinker. | Human/Teacher/child agents. | Variant build. |
| `scripts/build_openroad_variant_relink.py` | Recompile variant-owned `dpl_evolve` objects and relink a private OpenROAD binary from common-core link recipes. | `build_openroad_variant_relink.sh`. | Fast variant build. |

### Run And Evaluate

| Script | Purpose | Called by | Stage |
| --- | --- | --- | --- |
| `scripts/run_place_batch.sh` | Produce reusable `3_4_place_resized.odb` snapshots for selected cases. | Human/Teacher before baseline/evolve gates. | Input snapshot generation. |
| `scripts/run_canonical_line.sh` | Dispatch one canonical line: `openroad_dpl_flow` or `evolve_default`. | Humans, evaluator, Teacher loop. | Single run. |
| `scripts/compare_runs.py` | Compare two evaluator or metrics JSON files using stable metrics. | Human/Teacher review. | Result analysis. |

### Teacher/Child Optimization

| Script | Purpose | Called by | Stage |
| --- | --- | --- | --- |
| `scripts/optimize_case_with_codex.py` | Stable CLI shim for the multi-iteration Teacher/child optimization round. The implementation is split under `scripts/teacher_loop/`. | Human/Teacher. | Case-specific algorithm search. |
| `scripts/run_codex_exec.py` | Stable CLI shim for the low-level `codex exec --json` recorder used by launched Teacher/Student agents.  Can resume a prior Codex session with `--resume-session-id`; records usage and stderr category summaries. Implementation lives under `scripts/codex_exec/`. | `optimize_case_with_codex.py`. | Worker execution. |
| `scripts/watch_teacher_round.py` | Terminal or local-web dashboard for a Teacher/Student round.  Shows observable status, paths, last visible messages, diffs, metrics, and usage. | Human/Teacher. | Monitoring. |

`scripts/teacher_loop/` contains the Python implementation modules:
`orchestrator.py` for the top-level loop, `common.py` for shared data,
`evidence.py` for metrics and artifact validity, `prompts.py` for generated
prompt/packet material, and `execution.py` for Codex command execution and
source snapshots.

`scripts/codex_exec/` contains the low-level Codex recorder implementation:
`cli.py` for options, `runner.py` for the execution flow, and `artifacts.py`
for event/stderr/usage summaries.

Prompt text for the Teacher/child loop lives in
`prompt_templates/teacher_loop/`.  Python orchestration fills template
variables and writes generated packets; avoid burying long prompt prose inside
`optimize_case_with_codex.py`.

### References And Local Research

| Script | Purpose | Called by | Stage |
| --- | --- | --- | --- |
| `scripts/fetch_reference_papers.sh` | Fetch papers into the ignored local PDF cache. | Human/research agent when references are missing. | Local research setup only. |

### Baseline Harness

| Script | Purpose | Called by | Stage |
| --- | --- | --- | --- |
| `baseline/run_baseline.sh` | Strict canonical-line dispatcher. | `run_canonical_line.sh`, line wrappers, evaluator. | Baseline/evolve run. |
| `baseline/run_baseline_suite.sh` | Run the two canonical comparison lines as one suite. | Human/Teacher. | Baseline suite. |
| `baseline/run_openroad_dpl_flow.sh` | Convenience wrapper for `openroad_dpl_flow`. | Human/Teacher. | Baseline line. |
| `baseline/run_evolve_default.sh` | Convenience wrapper for `evolve_default`. | Human/Teacher/child validation. | Evolve line. |
| `baseline/detail_place_openroad.tcl` | OpenROAD Tcl driver for `detailed_placement`, `improve_placement`, `optimize_mirroring`. | `run_baseline.sh`. | Legalization command. |
| `baseline/detail_place_evolve.tcl` | OpenROAD Tcl driver for `detailed_placement_evolve`, `improve_placement_evolve`, `optimize_mirroring_evolve`. | `run_baseline.sh`. | Evolved legalization command. |
| `baseline/report_legalized_metrics.tcl` | Run `check_placement` or `check_placement_evolve`, placement parasitics, and ORFS `report_metrics` on the legalized ODB. | `run_baseline.sh`. | Post-legalization metrics. |
| `baseline/dpl_evolve_helpers.tcl` | Shared Tcl option parsing, path normalization, HPWL proxy, snapshots, and JSON helpers. | Baseline Tcl drivers. | Tcl helper library. |
| `baseline/collect_metrics.py` | Normalize run summaries, HPWL proxy, displacement, strict check result, and ORFS metrics into `metrics.json`. | `run_baseline.sh`. | Metrics normalization. |
| `baseline/flow_paths.py` | Python helper for resolving paths relative to `FLOW_HOME`. | Baseline Python scripts. | Baseline helper library. |
| `baseline/gen_orfs_metadata.py` | Normalize placement-only ORFS report metrics into a stable JSON. | Manual/debug baseline workflows. | Metrics helper. |

Old family-matrix/materializer scripts are not part of the default workflow
anymore.  Keep new automation focused on the constrained framework and the
Teacher/child case-optimization loop.

## Typical Framework Flow

1. Prepare ORFS once:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/prepare_workspace.sh" \
  --workspace-root "$ORFS_ROOT"
```

2. Build or reuse common OpenROAD core:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" 10
```

3. Create a candidate `dpl_evolve` source under `DPL_EVOLVE_STATE_ROOT`, relink,
   and run a canonical line with an explicit binary.

`prepare_workspace.sh` writes two seed snapshots when the patch sequence is
available from a clean anchor:

```text
$DPL_EVOLVE_STATE_ROOT/seed_sources/diamond_dpl_evolve
$DPL_EVOLVE_STATE_ROOT/seed_sources/framework_dpl_evolve
```

Use `--start-kind diamond` for direct/default DPL-code evolution and
`--start-kind framework` for the constrained top-framework evolution line.

The default evolved command remains `detailed_placement_evolve`.  Student
experiments use private `dpl_evolve` source trees and the lightweight variant
relink path.

## Teacher/Child Case Optimization

Create a reviewable optimization round without launching agents:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case jpeg_nangate45 \
  --start-kind framework \
  --children 4 \
  --iterations 2 \
  --dry-run \
  --audit-prompts
```

`--dry-run --audit-prompts` does not call Codex.  It writes prompts, generated
workspace/review packets, `PROMPT_AUDIT.md`, and `prompt_audit.json`.  The
audit flags agent-facing prompts that accidentally contain generated shell
commands, old dispatch wording, or excessive path noise.  Long exact commands
belong in `iter_XX/packet/*_workspace.md`, not in `iter_XX/prompts/*.md`.

Launch the teacher/child/review loop explicitly:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case jpeg_nangate45 \
  --prepare-workspace \
  --start-kind framework \
  --children 4 \
  --iterations 3 \
  --max-parallel 2 \
  --launch
```

Launch with per-student session continuity, explicit model settings, and more
parallel Student workers:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case jpeg_nangate45 \
  --start-kind framework \
  --children 4 \
  --iterations 5 \
  --max-parallel 4 \
  --model gpt-5.4 \
  --reasoning-effort xhigh \
  --resume-sessions \
  --launch
```

Follow-up prompts are compact by default after iteration 1. Each student also
keeps editing one stable active source workspace by default:

```text
.dpl_evolve_state/teacher_rounds/<round>/students/student_XX/workspace/variant/dpl_evolve
```

After every iteration, the orchestrator snapshots that source tree to:

```text
.dpl_evolve_state/teacher_rounds/<round>/students/student_XX/source_backups/iter_XX/dpl_evolve
```

Per-iteration diffs, build logs, and eval logs still live under
`students/student_XX/iter_XX/artifacts`.

`--prepare-workspace` is the one-flag bootstrap path for launched rounds.  It
runs `prepare_workspace.sh --workspace-root "$ORFS_ROOT"` before baseline
preflight, which refreshes the start-kind seed snapshots.  Use
`--prepare-force` only when it is safe to reset the prepared ORFS/OpenROAD
workspace.

The top-level orchestrator writes human-readable progress to:

```text
.dpl_evolve_state/teacher_rounds/<round>/round.log
.dpl_evolve_state/teacher_rounds/<round>/events.jsonl
```

Those files are the quickest way to verify whether baseline preflight,
prompt generation, Teacher launch, Student launch, source backup, review, and
prompt audit phases were reached.

For iteration 2 and later, the orchestrator also finds the best clean strict
candidate so far and pre-seeds `student_01` from that source backup.  This
keeps one protected elite-continuation branch alive while the other students
continue, cross-learn, or pivot.

Launched Teacher/Student sessions use the normal Codex session store.  The
orchestrator does not override `CODEX_HOME`; resume behavior comes from the
`thread_id` recorded in each operation summary plus `codex exec resume`.

Watch a running round in the terminal:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/watch_teacher_round.py" \
  jpeg_teacher_open_explore_4x5_gpt54_xhigh \
  --watch
```

Serve a tiny local dashboard:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/watch_teacher_round.py" \
  jpeg_teacher_open_explore_4x5_gpt54_xhigh \
  --serve --host 127.0.0.1 --port 8765
```

The dashboard shows observable work products only.  It cannot and should not
show hidden model reasoning; if we want more live visibility, the prompts should
ask students to write short progress notes or stage telemetry into artifacts.

The script is conservative by default: without `--launch`, it only writes the
round manifest and prompts under `DPL_EVOLVE_STATE_ROOT/teacher_rounds/`.
Each iteration has three phases:

1. Teacher planning prompt.
2. Student implementation prompts.
3. Teacher review prompt that reads all student artifacts, compares code
   changes side by side, compares metrics, and writes per-student continuation
   or pivot guidance.

Student lineage is tracked under `teacher_rounds/<round>/students/`, so later
iterations tell each student to continue its own implementation direction
instead of restarting from unrelated ideas.  Review statuses are guidance for
how to revise the next attempt; they do not freeze a student automatically.

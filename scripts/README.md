# Scripts

This directory contains the active helper scripts for the constrained
`detailed_placement_evolve` framework.

Runtime roots:

- `DPL_EVOLVE_AGENT_ROOT`
- `ORFS_ROOT`
- `DPL_EVOLVE_STATE_ROOT`

Use these environment variables for directory prefixes in tracked scripts,
docs, and generated packets. Machine-local absolute paths belong in ignored
`env.sh` or the caller environment.

## Script Inventory

Every active framework/helper script in `scripts/` is listed here.  If a file
is experiment-specific, keep it under `experiments/launchers/` or
`experiments/workbenches/` instead of this directory.

Active implementation files live under role namespaces such as `scripts/workspace/`, `scripts/evaluator/`, `scripts/matrix/`, `scripts/analysis/`, `scripts/calibration/`, `scripts/orchestration/`, `scripts/repo/`, and `scripts/bo/`. Top-level `scripts/` is reserved for two stable Python shims, `runtime_env.sh`, and this README.

### Workspace And Runtime

| Script | Purpose | Called by | Stage |
| --- | --- | --- | --- |
| `scripts/runtime_env.sh` | Resolve `DPL_EVOLVE_AGENT_ROOT`, `ORFS_ROOT`, `DPL_EVOLVE_STATE_ROOT`, and stable build aliases. | Sourced by shell entrypoints. | All shell-script stages. |
| `scripts/workspace/prepare_workspace.sh` | Prepare a clean ORFS/OpenROAD workspace by applying supported patches and snapshot reusable `dpl_evolve` seed sources. | Human/Teacher before experiments. | Bootstrap. |
| `scripts/repo/case_registry.py` | Resolve cases from the single `problems/` registry. | `run_place_batch.sh`, `run_baseline.sh`, Teacher tooling, humans. | Case selection. |
| `scripts/repo/query_knowledge.py` | Query and validate the concise skill-card index. | Teacher/Student packets, humans. | Knowledge lookup. |
| `scripts/repo/checkpoint.py` | Snapshot/restore local candidate source state under ignored runtime state. | Teacher/child loop and manual recovery. | Experiment state management. |
| `scripts/repo/audit_repo_hygiene.py` | Check that GitHub-facing files avoid stale family-flow references and unclassified patch artifacts. | Human/CI-style preflight. | Repo hygiene. |
| `scripts/repo/check_release_readiness.sh` | Run the static release gate: compile, shell syntax, knowledge validation, repo hygiene, Teacher dry-run prompt audit, and generated Student script syntax. | Human/CI-style preflight. | Release gate. |

### Build And Relink

| Script | Purpose | Called by | Stage |
| --- | --- | --- | --- |
| `scripts/workspace/configure_openroad_core.sh` | Write common-core `core_env.sh` with build/install/binary paths. | Human/Teacher before common-core build. | Common-core configure. |
| `scripts/workspace/build_openroad_core.sh` | Choose the common-core root and delegate the actual OpenROAD build. | Human/Teacher before variants. | Common-core build. |
| `scripts/workspace/build_openroad_only.sh` | Single OpenROAD configure/build/install implementation. | `build_openroad_core.sh`, evaluator, advanced manual builds. | Common-core or explicit OpenROAD build. |
| `scripts/workspace/configure_openroad_variant_relink.sh` | Write `variant_env.sh` for a private candidate `dpl_evolve` source. | Human/Teacher/child agents. | Variant configure. |
| `scripts/workspace/build_openroad_variant_relink.py` | Recompile variant-owned `dpl_evolve` objects and relink a private OpenROAD binary from common-core link recipes. | Human/Teacher/child agents. | Fast variant build. |

### Run And Evaluate

| Script | Purpose | Called by | Stage |
| --- | --- | --- | --- |
| `scripts/evaluator/run_place_batch.sh` | Produce reusable `3_4_place_resized.odb` snapshots for selected cases. | Human/Teacher before baseline/evolve gates. | Input snapshot generation. |
| `scripts/calibration/calibrate_start_seeds.sh` | Build/evaluate active prepared start-kind seeds `framework`, `diamond`, and `default_negotiation` on one target case, then write initial donor-evidence tables. This is a target-local start-kind probe, not Level 1 calibration. | `optimize_case_with_codex.py --calibrate-start-seeds`, Human/Teacher. | Target start-kind probe. |
| `scripts/calibration/summarize_start_seed_calibration.py` | Summarize target start-kind probe candidate matrices into markdown/TSV stage-wise metrics. | `calibrate_start_seeds.sh`. | Result analysis. |
| `scripts/matrix/run_candidate_matrix.sh` | Build one fixed candidate `dpl_evolve` source once, then evaluate that identical code across every enabled row in a TSV plan. | Human/Teacher after a promising exported student source commit exists. | Cross-case candidate validation. |
| `scripts/matrix/run_round_candidate_matrices.sh` | Enumerate committed student source revisions from one Teacher round, export each revision, and run `run_candidate_matrix.sh` for each. | Human/Teacher after a completed round. | 4xN candidate validation. |
| `scripts/analysis/export_round_candidate_sources.py` | Export committed student source revisions from one Teacher round into reusable source snapshots. | `run_round_candidate_matrices.sh`, Human/Teacher. | Candidate export. |
| `scripts/evaluator/normalize_candidate_matrix_results.py` | Normalize candidate-matrix result TSVs into stable comparison tables. | `run_round_candidate_matrices.sh`, Human/Teacher. | Result analysis. |
| `scripts/evaluator/run_canonical_line.sh` | Dispatch one canonical line: `openroad_dpl_flow`, `openroad_dpl_negotiation`, or `evolve_default`. | Humans, evaluator, Teacher loop. | Single run. |
| `scripts/bo/bo_tune_case.py` | Ray Tune black-box optimize Tcl command parameters for one case using the same strict baseline runner and metrics.json as the white-box evolve loop. Requires Ray Tune; there is no local fallback. | Human/Teacher for black-box baselines. | Parameter tuning / ablation. |
| `scripts/bo/setup_raytune_venv.sh` | Create the repo-local `.venv_raytune` environment and verify `ray.tune` plus `optuna`. | Human before BO runs. | BO setup. |
| `scripts/analysis/compare_runs.py` | Compare two evaluator or metrics JSON files using stable metrics. | Human/Teacher review. | Result analysis. |
| `scripts/evaluator/report_candidate_metrics.py` | Summarize one candidate run into canonical final/stage metrics, artifact paths, and key log counter lines so Students do not need to hand-parse nested metrics/log files. | Student helpers, Human/Teacher review. | Candidate result summary. |
| `scripts/analysis/report_experiment_quick_status.py` | Fast state-only batch summary from round packets and Student metric summaries. | Human/Teacher monitoring. | Monitoring/result analysis. |
| `scripts/evaluator/report_stage_metrics.py` | Print canonical per-round stage-wise HPWL/runtime/displacement rows from evaluator `metrics.json`, falling back to labeled partial DPL logs for in-flight evidence. | Human/Teacher review, packets. | Result analysis. |
| `scripts/analysis/report_experiment_status.py` | Summarize a launch directory: active processes, completed/active rounds, best baseline vs best evolved donors, and optional detailed stage rows. | Human/Teacher monitoring. | Monitoring/result analysis. |

### Teacher/Child Optimization

| Script | Purpose | Called by | Stage |
| --- | --- | --- | --- |
| `scripts/optimize_case_with_codex.py` | Stable CLI shim for the multi-iteration Teacher/child optimization round. The implementation is split under `scripts/teacher_loop/`. | Human/Teacher. | Case-specific algorithm search. |
| `scripts/run_codex_exec.py` | Stable CLI shim for the low-level `codex exec --json` recorder used by launched Teacher/Student agents.  Can resume a prior Codex session with `--resume-session-id`; records usage and stderr category summaries. Implementation lives under `scripts/codex_exec/`. | `optimize_case_with_codex.py`. | Worker execution. |
| `scripts/orchestration/watch_teacher_round.py` | Terminal or local-web dashboard for a Teacher/Student round. | Human/Teacher. | Monitoring. |
| `scripts/orchestration/check_evolve_now.py` | Compact live status for active experiment batches. | Human/Teacher. | Monitoring. |
| `scripts/orchestration/monitor_evolve_heartbeat.sh` | Repeated batch heartbeat for long-running campaigns. | Human/Teacher. | Monitoring. |
| `scripts/analysis/compact_round_peer_prompts.py` | Compact large peer-prompt context from a Teacher round into smaller review artifacts. | Human/Teacher when prompt context grows too large. | Prompt hygiene. |

### Experiment-Specific Launchers

Experiment-specific launch scripts are intentionally outside `scripts/` so
Teacher/Student agents do not treat them as generic framework tools:

```text
experiments/launchers/
experiments/workbenches/
```

Current launchers:

| Script | Purpose |
| --- | --- |
| `experiments/launchers/run_aggressive_flow_knowledge_experiments.sh` | Historical flow-knowledge batch driver from a TSV plan. |
| `experiments/launchers/run_jpeg_util60_discovery_then_matrix.sh` | JPEG util60 discovery plus fixed-candidate matrix pipeline. |
| `experiments/launchers/run_openroad_dpl_9case_baselines.sh` | 9-case OpenROAD DPL baseline batch. |
| `experiments/launchers/run_bo_8case_openroad_dpl.sh` | 8-case OpenROAD native DPL BO sweep. |
| `experiments/launchers/run_bo_9case_openroad_dpl.sh` | 9-case OpenROAD native DPL BO sweep. |
| `experiments/launchers/run_evolve_9case_place_batch.sh` | 9-case Teacher/Student evolve sweep. |
| `experiments/launchers/run_evolve_9case_breadth16x4_place_batch.sh` | Wider 9-case Teacher/Student evolve campaign with breadth-16/iteration-4 settings. |
| `experiments/launchers/run_best_evolved_9case_transfer_matrix.sh` | Best-evolved source transfer matrix launcher for cross-case reuse checks. |
| `experiments/workbenches/prepare_negotiation_patch_repair_workbench.sh` | Dedicated evolved-negotiation patch repair workbench generator. |

Experiment-specific analysis utilities live under `experiments/analysis/`;
keep new one-off paper/campaign reducers there instead of under generic
`scripts/analysis/`.

`scripts/teacher_loop/` contains the Python implementation modules:
`orchestrator.py` for the top-level loop, `common.py` for shared data,
`evidence.py` for metrics and artifact validity, `context_packets.py` for
generated context and route packets, `packet_builders.py` for generated
workspace/review packets, `prompt_rendering.py` for agent-facing prompt text
and prompt audit, `workspace_scripts.py` for start-kind and generated Student
helper-script APIs, and `execution.py` for Codex command execution and source
commits. `prompt_rendering.py` now owns prompt-safe text excerpting and audit
rules plus Teacher/Student prompt construction, `packet_builders.py` owns
packet/README generation, and `context_packets.py` owns Teacher/Student
context generation and route-insight packets. `workspace_scripts.py` owns start-kind source resolution,
parent-source selection, runtime timeout policy, executable-script writing, and
generated Student helper scripts. `prompts.py` remains a legacy compatibility
import module; new code should import through the role-specific modules.

`scripts/codex_exec/` contains the low-level Codex recorder implementation:
`cli.py` for options, `runner.py` for the execution flow, and `artifacts.py`
for event/stderr/usage summaries.

Prompt text for the Teacher/child loop lives in
`prompt_templates/teacher_loop/`.  Python orchestration fills template
variables and writes generated packets; avoid burying long prompt prose inside
`optimize_case_with_codex.py`.

Student workspace packets point to iteration-specific generated scripts such as
`scripts/iter_XX/00_prepare_source.sh`,
`scripts/iter_XX/10_build_variant.sh`,
`scripts/iter_XX/20_evaluate_candidate.sh`,
`scripts/iter_XX/21_report_candidate_metrics.sh`,
`scripts/iter_XX/25_trial_source.sh`, and
`scripts/iter_XX/30_finalize_source.sh` under each Student workspace. Students
should run those scripts instead of reconstructing relink, evaluator, git, or
diff commands from memory.

Result tables and Teacher packets should use `metrics.json:hpwl` as canonical
HPWL. That field is parsed from OpenROAD/DPL pin-based log reports. The legacy
bbox `hpwl_proxy` field is diagnostic only.

### Black-Box Parameter Tuning

Use `scripts/bo/bo_tune_case.py` when we need a black-box comparison against the
white-box Agent/code-evolution flow.  This runner requires Ray Tune/Optuna and
intentionally has no local fallback.  The tuner does not edit source code or
relink OpenROAD.  It injects parameter lists into the existing baseline Tcl
drivers through the environment prefix declared in the YAML search space.
OpenROAD native DPL BO uses:

```text
OPENROAD_DPL_DETAIL_ARGS
OPENROAD_DPL_IMPROVE_ARGS
OPENROAD_DPL_OPTIMIZE_ARGS
```

Set up the local Ray Tune Python once:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/bo/setup_raytune_venv.sh"
```

Single-case example:

```bash
"$DPL_EVOLVE_AGENT_ROOT/.venv_raytune/bin/python" "$DPL_EVOLVE_AGENT_ROOT/scripts/bo/bo_tune_case.py" \
  --case aes_dense_nangate45 \
  --flow-variant DENSE \
  --space "$DPL_EVOLVE_AGENT_ROOT/configs/bo_search_spaces/openroad_dpl_native.yaml" \
  --run-id bo_aes_dense_openroad_dpl_100 \
  --trials 100 \
  --max-concurrent-trials 4 \
  --threads 10
```

Standard 8-case sweep:

```bash
BO_TRIALS=100 BO_MAX_CONCURRENT_TRIALS=4 BO_THREADS_PER_TRIAL=10 \
  "$DPL_EVOLVE_AGENT_ROOT/experiments/launchers/run_bo_8case_openroad_dpl.sh"
```

Standard 9-case sweep for the shared `place_batch_20260421_220319` snapshots:

```bash
BO_TRIALS=400 BO_MAX_CONCURRENT_CASES=3 BO_MAX_CONCURRENT_TRIALS=4 \
BO_THREADS_PER_TRIAL=10 BO_FLOW_VARIANT=place_batch_20260421_220319 \
  "$DPL_EVOLVE_AGENT_ROOT/experiments/launchers/run_bo_9case_openroad_dpl.sh"
```

DPO-boundary sweep with the native legalizer fixed and a wider
`improve_placement` search space:

```bash
BO_SPACE="$DPL_EVOLVE_AGENT_ROOT/configs/bo_search_spaces/openroad_dpl_native_dpo_frontier.yaml" \
BO_RUN_PREFIX=openroad_dpl_native_dpo_frontier_9case_bo \
BO_TRIALS=400 BO_MAX_CONCURRENT_CASES=3 BO_MAX_CONCURRENT_TRIALS=4 \
BO_THREADS_PER_TRIAL=10 BO_FLOW_VARIANT=place_batch_20260421_220319 \
  "$DPL_EVOLVE_AGENT_ROOT/experiments/launchers/run_bo_9case_openroad_dpl.sh"
```

This DPO-focused space explores `improve_placement -random_seed`, scalar and
two-dimensional DPO displacement windows, `-enable_extra_dpl`, and the
GlobalSwapParams that remain effective despite the native internal DPO script
hardcoding `gs -p 10 -t 0.005`.  It is intended to show the public-knob
boundary of DPO, not to replace source-level white-box evolution.

OpenROAD default DPL baseline rows for the same 9-case set:

```bash
BASELINE_FLOW_VARIANT=place_batch_20260421_220319 BASELINE_MAX_PARALLEL=3 \
  "$DPL_EVOLVE_AGENT_ROOT/experiments/launchers/run_openroad_dpl_9case_baselines.sh"
```

White-box Agent evolve rows for the same 9-case set:

```bash
EVOLVE_FLOW_VARIANT=place_batch_20260421_220319 EVOLVE_CHILDREN=4 \
EVOLVE_ITERATIONS=15 EVOLVE_TEACHER_MODEL=gpt-5.4 \
EVOLVE_TEACHER_REASONING_EFFORT=xhigh EVOLVE_STUDENT_MODEL=gpt-5.4 \
EVOLVE_STUDENT_REASONING_EFFORT=xhigh EVOLVE_MAX_CONCURRENT_CASES=3 \
  "$DPL_EVOLVE_AGENT_ROOT/experiments/launchers/run_evolve_9case_place_batch.sh"
```

The 9-case sweep checks that every case has
`results/<platform>/<design>/place_batch_20260421_220319/3_4_place_resized.odb`
before launching BO.  If one snapshot is still being generated, the script
fails before starting any BO jobs.

Outputs are written under:

```text
$DPL_EVOLVE_STATE_ROOT/bo_runs/<run-id>/
```

Key artifacts:

- `trials.jsonl`: resumable full ledger, including failed trials.
- `trials.tsv`: compact spreadsheet-style summary.
- `best.json`: current best clean legal trial by lowest final HPWL only.
- `best_value.json`: current best clean legal trial by `G_HR`; use this only to
  discuss runtime value, not as the headline HPWL result.
- `config.json`: exact run configuration.

The human-facing value score is higher-is-better:

```text
G_HR = 100 * (HPWL_ref - HPWL_trial) / HPWL_ref
     - P(runtime_trial / runtime_ref)

P(r) = 0, if r <= 1.10
P(r) = 1.0 * (sqrt(r) - sqrt(1.10)) / (sqrt(2.0) - sqrt(1.10)), otherwise
```

Baseline has `G_HR = 0`; higher is better.  HPWL remains the primary objective;
the HPWL term is normalized by `HPWL_ref`, and the runtime term is a value check:
runtime speedups and <=1.10x runtime noise receive no bonus, and a
2x-slower setting must buy 1.0 reference-normalized final-HPWL percentage
points of reduction to break even.  Ray Tune minimizes `score = HPWL_final`;
`G_HR` is reported in `trials.tsv` and `best_value.json` so a faster but
worse-HPWL point cannot replace the HPWL-best result.

The default DSE strategy is not pure random search.  Each run first evaluates a
small deterministic mechanism-anchor set: OpenROAD default, window-only DPL,
incremental+global-swap, extra-DPL+global-swap, fast local-window, and large
window configurations.  It then spends `min(25, max(10, trials/4))` startup
trials on broad mixed discrete/continuous exploration, followed by Optuna TPE
with parallel-aware constant-liar suggestions for exploitation.  Override
`BO_ANCHOR_STRATEGY`, `BO_STARTUP_TRIALS`, or `BO_TPE_CANDIDATES` only when a
case has a known reason to need a different exploration/exploitation split.

The default OpenROAD DPL search space is
`configs/bo_search_spaces/openroad_dpl_native.yaml`.  Edit that YAML to change
parameter ranges before running a new BO sweep.

### References And Local Research

| Script | Purpose | Called by | Stage |
| --- | --- | --- | --- |
| `scripts/analysis/fetch_reference_papers.sh` | Fetch papers into the ignored local PDF cache. | Human/research agent when references are missing. | Local research setup only. |

### Baseline Harness

| Script | Purpose | Called by | Stage |
| --- | --- | --- | --- |
| `baseline/run_baseline.sh` | Strict canonical-line dispatcher. | `run_canonical_line.sh`, canonical line scripts, evaluator. | Baseline/evolve run. |
| `baseline/run_baseline_suite.sh` | Run the three canonical comparison lines as one suite. | Human/Teacher. | Baseline suite. |
| `baseline/run_openroad_dpl_flow.sh` | Convenience wrapper for `openroad_dpl_flow`. | Human/Teacher. | Baseline line. |
| `baseline/run_openroad_dpl_negotiation.sh` | Convenience wrapper for `openroad_dpl_negotiation`. | Human/Teacher. | Baseline line. |
| `baseline/run_evolve_default.sh` | Convenience wrapper for `evolve_default`. | Human/Teacher/child validation. | Evolve line. |
| `baseline/detail_place_openroad.tcl` | OpenROAD Tcl driver for `detailed_placement`, `improve_placement`, `optimize_mirroring`. | `run_baseline.sh`. | Legalization command. |
| `baseline/detail_place_evolve.tcl` | OpenROAD Tcl driver for `detailed_placement_evolve`, `improve_placement_evolve`, `optimize_mirroring_evolve`. | `run_baseline.sh`. | Evolved legalization command. |
| `baseline/report_legalized_metrics.tcl` | Run `check_placement` or `check_placement_evolve`, placement parasitics, and ORFS `report_metrics` on the legalized ODB. | `run_baseline.sh`. | Post-legalization metrics. |
| `baseline/dpl_evolve_helpers.tcl` | Shared Tcl option parsing, path normalization, HPWL proxy, snapshots, and JSON helpers. | Baseline Tcl drivers. | Tcl helper library. |
| `baseline/collect_metrics.py` | Normalize run summaries, OpenROAD/DPL pin-based HPWL, legacy HPWL proxy, displacement, strict check result, and ORFS metrics into `metrics.json`. | `run_baseline.sh`. | Metrics normalization. |
| `baseline/flow_paths.py` | Python helper for resolving paths relative to `FLOW_HOME`. | Baseline Python scripts. | Baseline helper library. |
| `baseline/gen_orfs_metadata.py` | Normalize placement-only ORFS report metrics into a stable JSON. | Manual/debug baseline workflows. | Metrics helper. |

Old family-matrix/materializer scripts are not part of the default workflow
anymore.  Keep new automation focused on the constrained framework and the
Teacher/child case-optimization loop.

## Typical Framework Flow

Run the repo-level static release gate before launching expensive ORFS work:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/repo/check_release_readiness.sh"
```

Use `--skip-teacher-dry-run` only when ORFS/OpenROAD roots are not available
and a static-only check is needed.

1. Prepare ORFS once:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/prepare_workspace.sh" \
  --workspace-root "$ORFS_ROOT"
```

2. Build or reuse common OpenROAD core:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/configure_openroad_core.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/workspace/build_openroad_core.sh" --threads 10
```

3. Create a candidate `dpl_evolve` source under `DPL_EVOLVE_STATE_ROOT`, relink,
   and run a canonical line with an explicit binary.

`prepare_workspace.sh` writes seed snapshots when the patch sequence is
available from a clean anchor:

```text
$DPL_EVOLVE_STATE_ROOT/seed_sources/diamond_dpl_evolve
$DPL_EVOLVE_STATE_ROOT/seed_sources/framework_dpl_evolve
```

Use the orchestrator default `--start-kind framework` for the current
constrained source framework. Use
`--start-kind diamond` only as an explicit contrast or ablation against the
framework start point. Use `--start-kind default_negotiation` when Teacher
assigns the negotiation route as the source parent for the current case.

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
.dpl_evolve_state/<round>/teacher_rounds/students/student_XX/workspace/variant/dpl_evolve
```

That source directory is a local git repository. Each Student keeps a stable dev
branch such as `dev/student_01`; each launched iteration records an
`iteration/<run_tag>` ref as the diff base. The student should commit its final
source state. The orchestrator creates a fallback commit only when source
changes remain uncommitted, then records the revision at:

```text
.dpl_evolve_state/<round>/teacher_rounds/students/student_XX/iter_XX/artifacts/source_commit.json
```

The same commit is also pinned to a stable local branch such as
`candidate/<round>_iter_03_student_01_<case>`. Later workspace reseeding keeps
the git repository and these candidate refs, so elite continuation and matrix
export can inherit the exact evaluated source instead of relying on a mutable
dev branch.

Generated workspaces include helper scripts for this branch workflow:

- `00_prepare_source.sh` creates/reuses the private source repo, switches to the
  generated Student dev branch, and records the iteration-start ref/base commit.
- `01_prepare_start_source.sh --kind <kind>` atomically prepares and switches
  from a prepared start branch.
- `02_source_status.sh` prints current branch, base commit, candidate refs, and
  start branches.
- `03_fetch_peer_source.sh --peer-repo <repo> --peer-ref <ref>` fetches a peer
  candidate into `peer/<label>` and writes diff artifacts without changing the
  working tree.
- `25_trial_source.sh begin|keep|reject|status` owns checkpoint, kept, and
  rejected branch handling. `begin --from-ref <ref>` starts a repair trial from
  a prior kept/rejected ref. Reject commits and pins rejected evidence but
  leaves the code checked out on the dev branch; use
  `04_switch_start_branch.sh --ref <ref>` or `--kind <kind>` for intentional
  dev-branch resets.
- `30_finalize_source.sh` commits the final dev source, pins the stable
  candidate ref used by elite continuation/export, writes the implementation
  diff from iteration-start to final dev HEAD, and seeds the knowledge card
  skeleton if needed.

Per-iteration diffs, build logs, and eval logs still live under
`students/student_XX/iter_XX/artifacts`.

Generated Student command packets also include `08_query_knowledge.sh`, a thin
wrapper around `scripts/repo/query_knowledge.py`. Use it for LEGO-lite stage skill
lookup instead of broad-reading the whole knowledge tree.

`--prepare-workspace` is the one-flag bootstrap path for launched rounds.  It
runs `prepare_workspace.sh --workspace-root "$ORFS_ROOT"` before baseline
preflight, which refreshes the start-kind seed snapshots.  Use
`--prepare-force` only when it is safe to reset the prepared ORFS/OpenROAD
workspace.

Use `--calibrate-start-seeds` when Teacher should see target-local initial
full-flow results for the prepared start-kind seeds before assigning Student
routes. This is not paper-level Level 1 calibration; see
`$DPL_EVOLVE_AGENT_ROOT/calibration/README.md` for the Level 1 contract.

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case jpeg_nangate45 \
  --flow-variant place_batch_20260421_220319 \
  --round-id jpeg_start_calibration_probe \
  --prepare-workspace \
  --calibrate-start-seeds \
  --children 4 \
  --iterations 1 \
  --launch
```

The target start-kind probe packet is written to:

```text
$DPL_EVOLVE_STATE_ROOT/<round>/teacher_rounds/iter_XX/packet/start_seed_calibration.md
$DPL_EVOLVE_STATE_ROOT/<round>/start_seed_calibration/start_seed_calibration.tsv
```

The top-level orchestrator writes human-readable progress to:

```text
.dpl_evolve_state/<round>/teacher_rounds/round.log
.dpl_evolve_state/<round>/teacher_rounds/events.jsonl
```

Those files are the quickest way to verify whether baseline preflight,
prompt generation, Teacher launch, Student launch, source commit, review, and
prompt audit phases were reached.

For iteration 2 and later, the orchestrator also finds the best clean strict
candidate so far and pre-seeds `student_01` from that exported source commit.  This
keeps one protected elite-continuation branch alive while the other students
continue, cross-learn, or pivot.

Launched Teacher/Student sessions use the normal Codex session store, usually
`~/.codex` unless `CODEX_HOME` is explicitly set. `scripts/run_codex_exec.py`
checks that the selected store is writable before starting Codex; if it is not
writable, the operation fails so the environment can be fixed directly.

The chosen store and reason are recorded in `codex_invocation.json`,
`codex_usage_summary.json`, and each worker's session state. Later runs reuse
the recorded thread id only when it is visible in the same selected store.

Each Teacher/Student workspace stores its identity and last thread id:

```text
.dpl_evolve_state/<round>/teacher_rounds/teacher_workspace/.codex_session_state.json
.dpl_evolve_state/<round>/teacher_rounds/students/student_XX/workspace/.codex_session_state.json
```

`scripts/run_codex_exec.py` auto-resumes from that state file when it contains
a recorded `last_thread_id`.

Watch a running round in the terminal:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/orchestration/watch_teacher_round.py" \
  <round_id> \
  --watch
```

Serve a tiny local dashboard:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/orchestration/watch_teacher_round.py" \
  <round_id> \
  --serve --host 127.0.0.1 --port 8765
```

The dashboard shows observable work products only.  It cannot and should not
show hidden model reasoning; if we want more live visibility, the prompts should
ask students to write short progress notes or stage telemetry into artifacts.

The script is conservative by default: without `--launch`, it only writes the
round manifest and prompts under `DPL_EVOLVE_STATE_ROOT/<round>/teacher_rounds/`.
Each iteration has three phases:

1. Teacher planning prompt.
2. Student implementation prompts.
3. Teacher review prompt that reads all student artifacts, compares code
   changes side by side, compares metrics, and writes per-student continuation
   or pivot guidance.

Student lineage is tracked under `<round>/teacher_rounds/students/`, so later
iterations tell each student to continue its own implementation direction
instead of restarting from unrelated ideas.  Review statuses are guidance for
how to revise the next attempt; they do not freeze a student automatically.

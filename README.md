# dpl_evolve_agent

This README is for humans: setup, quick start, and the basic project model.
The Codex/agent execution contract lives in `AGENTS.md`.

`dpl_evolve_agent` is a standalone control repo for evolving
`tools/OpenROAD/src/dpl_evolve` without forking or modifying a large ORFS tree
more than necessary.

The short version:

- ORFS stays external.
- This repo stores prompts, scripts, patches, skills, and evaluator glue.
- Runtime state defaults to this repo's ignored `.dpl_evolve_state/`.
- The primary evolved placement command is always `detailed_placement_evolve`.
- The current algorithm direction is a constrained top-level framework whose
  stages can be replaced by agents, not an unconstrained family-tree router.
- The listed stages are scaffolding. Specific objectives, algorithms, and
  stage order remain evidence-driven and may change per case.
- OpenROAD common code is built once.
- Each experiment variant rebuilds only its own `dpl_evolve` code and relinks a
  private `openroad` binary.

## Project Goal

The goal is case-level algorithm evolution for detailed placement.  Teacher
and child agents may change algorithms, stage policies, objectives, and CPU
implementation details as long as the result is judged by independent metrics
and strict legality checks.  The command under evolution stays:

```text
detailed_placement_evolve
```

Diamond/OpenROAD, NBLG/negotiation, LEGALM, and DREAMPlace/Abacus code are
references or baselines.  They are not global truth; every borrowed mechanism
must earn its place on the active case through measured HPWL/runtime/
displacement/legality evidence.

## Basic Layout

Recommended sibling layout:

```text
work/
  OpenROAD-flow-scripts/
  dpl_evolve_agent/
    .dpl_evolve_state/   # ignored runtime state
```

Recommended local setup:

```bash
cp env.sh.example env.sh
$EDITOR env.sh
source env.sh
```

`env.sh` is ignored by git. Keep machine-specific paths there, not in tracked
scripts or docs. The default `DPL_EVOLVE_STATE_ROOT` is
`$DPL_EVOLVE_AGENT_ROOT/.dpl_evolve_state`; use another local path only if you
need a larger scratch filesystem.

Case facts have one source of truth:

```text
problems/<case>/problem.yaml
```

Batch scripts may use named lists from `problems/case_sets.json`, but those
lists contain only case ids. They do not duplicate design configs or platform
facts.

## Prepare ORFS

Prepare applies the small ORFS/OpenROAD overlay needed by this project,
including the clean `dpl_evolve` source and the constrained framework patch:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/prepare_workspace.sh" \
  --workspace-root "$ORFS_ROOT"
```

This should not turn ORFS into the control repo. The agent remains standalone.

If you made a local ORFS clone and its relative OpenROAD submodule URL points
at a missing sibling path, set a local override in `env.sh`:

```bash
export DPL_EVOLVE_OPENROAD_URL=https://github.com/The-OpenROAD-Project/OpenROAD.git
```

## Prepare Place Snapshots

The strict evaluator reuses an existing placement snapshot:

```text
flow/results/<platform>/<design>/<FLOW_VARIANT>/3_4_place_resized.odb
```

Create snapshots with:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/run_place_batch.sh"
```

If snapshots already exist, you can reuse their `FLOW_VARIANT`.

## Build Fast

Build common OpenROAD core once:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" 10
```

The reusable common core is stored under the agent state root, for example:

```text
dpl_evolve_agent/.dpl_evolve_state/openroad_core/<prepared-openroad-sha>/
```

The upstream OpenROAD anchor itself does not contain `src/dpl_evolve`; run the
prepare step first so the OpenROAD submodule is at the local prepared commit.

Create one private variant source and binary:

```bash
mkdir -p "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent"

"$DPL_EVOLVE_AGENT_ROOT/scripts/create_variant_start.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent" \
  --dpl-src "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/dpl_evolve"

"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent" \
  --dpl-src "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/dpl_evolve"

"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent" \
  --dpl-src "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/dpl_evolve" \
  --threads 10
```

The variant build produces:

```text
${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/install/OpenROAD/bin/openroad
${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/install/OpenROAD/bin/sta
```

`sta` is symlinked from the common-core build when available.

## Run One Evaluation

Use an explicit binary for variant runs:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/evaluator.py" \
  --case gcd_nangate45 \
  --mode single \
  --line evolve_default \
  --flow-variant <FLOW_VARIANT_WITH_3_4_PLACE_RESIZED_ODB> \
  --run-tag smoke_gcd \
  --skip-build \
  --openroad-binary "${DPL_EVOLVE_STATE_ROOT}/variants/test_agent/install/OpenROAD/bin/openroad" \
  --out "${DPL_EVOLVE_STATE_ROOT}/checkpoints/operations/smoke_gcd/eval.json"
```

Read:

```text
flow/reports/<platform>/<design>/<FLOW_VARIANT>/dpl_evolve_baseline/<run_tag>/metrics.json
```

## Source References

Future agents should learn from compact reference implementations instead of
wandering through historical experiments:

```text
family_variants/
```

That directory keeps the high-value donors:

- OpenROAD diamond DPL,
- OpenROAD negotiation / NBLG,
- LEGALM staged legalization,
- DREAMPlace Abacus.

Use `knowledge/EVIDENCE_POLICY.md` to separate project contracts, measured
observations, working hypotheses, and reference donors. The current
strict-track comparison anchor is the OpenROAD DPL flow line
(`detailed_placement`, `improve_placement`, `optimize_mirroring`). Diamond,
LEGALM, Negotiation/NBLG, and DREAMPlace/Abacus are donors whose mechanisms
must be validated after porting.

## Repository Hygiene

Before publishing or asking another agent to read the repo, run:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/audit_repo_hygiene.py"
git diff --check
```

Tracked files must be deployable from a fresh clone:

- no machine-local absolute paths,
- no runtime state or build products,
- no hidden dependency on ignored archives,
- no stale family-tree patch surfaces,
- no evaluator/scoring changes disguised as algorithm changes.

Runtime evidence belongs under ignored `DPL_EVOLVE_STATE_ROOT`; durable lessons
belong in `knowledge/`, `family_variants/`, or the database
helpers with explicit evidence scope.

Older family variants remain as archived evidence, but the default development
path is now:

```text
detailed_placement_evolve
  -> EvolveLegalizer top-level framework
  -> agent-modified stage implementation
  -> strict evaluator
  -> database evidence commit
```

## Run The Teacher/Child Optimization Loop

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/optimize_case_with_codex.py" \
  --case jpeg_nangate45 \
  --children 4 \
  --iterations 2 \
  --dry-run
```

This creates a reviewable Teacher/child optimization round under ignored
`DPL_EVOLVE_STATE_ROOT/teacher_rounds/`.  Add `--launch` when you want it to
invoke `codex exec` through `scripts/run_codex_exec.py`.

At the beginning of a launched round, the orchestrator refreshes the canonical
baseline suite for the case:

```text
openroad_dpl_flow
evolve_default
```

The generated Teacher prompt includes the metrics, report, result, and log
paths for each row so Teacher can inspect evidence before assigning aggressive
student routes.

Teacher review is intentionally cross-student: it reads each student's code
diff and metrics, compares mechanisms side by side, and gives every student a
next revision or pivot.  A weak result is not a frozen worker; it becomes a
directed follow-up inside that student's private variant workspace.

The Codex-facing contract is in:

```text
AGENTS.md
```

## Basic Principles

- Keep `dpl` upstream-clean.
- Evolve only `dpl_evolve`.
- Keep this repo standalone.
- Keep ORFS edits minimal and patch-based.
- Use common-core plus variant relink for fast parallel experiments.
- Always bind explicit `openroad` binaries for variant/family runs.

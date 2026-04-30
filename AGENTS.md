# AGENTS.md

This file is the execution contract for coding agents.  For human setup, use
`README.md`.

## Runtime Roots

- `DPL_EVOLVE_AGENT_ROOT`: this control repo.
- `ORFS_ROOT`: the external OpenROAD-flow-scripts workspace.
- `DPL_EVOLVE_STATE_ROOT`: ignored runtime state, builds, checkpoints,
  operations, and private variant binaries.

Machine-local values belong in ignored `env.sh`.  Do not hardcode local paths
in tracked scripts, prompts, or patches.

ORFS is the interaction workspace.  Agents may read it and may write runtime
artifacts under `DPL_EVOLVE_STATE_ROOT`, but durable source-of-truth changes
belong in this repo as patches, docs, or database records.

## Current Direction

The active project direction is a constrained top-level detailed-placement
framework.  The primary evolved placement command is always:

```text
detailed_placement_evolve
```

Do not revive the old family-tree router unless explicitly assigned.  Legacy
family-flow notes, matrices, routers, and robustness reports are intentionally
excluded from default tracked context so they do not pollute agent prompts.

The current source patch is:

```text
patches/openroad_dpl_evolve_framework.patch
```

It introduces the `EvolveLegalizer` hook surface behind
`detailed_placement_evolve`:

1. import design context,
2. call a student-owned algorithm hook,
3. expose optional donor callbacks for code that intentionally uses them,
4. emit stage telemetry.

This is a strong starting framework, not a final algorithm. The prepared source
runs a concrete LEGALM-style guidance/legalization path and can use
Abacus-enabled negotiation repair when needed. Agents are expected to modify,
replace, or reorder those stages aggressively inside private variant source,
then the strict evaluator judges the result against a separately measured
OpenROAD DPL flow baseline.

## Reference Sources

Use the compact donor shelf, not old experiment directories:

```text
family_variants/
family_variants/REFERENCE_INDEX.yaml
```

Canonical donors:

- OpenROAD DPL flow: current strict-track comparison anchor
  (`detailed_placement`, `improve_placement`, `optimize_mirroring`).
- OpenROAD diamond DPL: local-search donor and prepass reference, not the
  current standalone baseline runner.
- OpenROAD negotiation/NBLG: repair and overflow donor; do not assume it is the
  right primary engine for every case.
- OpenROAD negotiation/NBLG also includes selected threaded-frontier mechanism
  deltas from older experiments.
- LEGALM-guidance source reference: staged relaxed legalization / ALM-style
  donor for the active framework.
- DREAMPlace Abacus: row assignment and compaction donor.

If you need old algobank/family evidence, the task must provide or name that
archive explicitly. Do not broad-read external or ignored archival material by
default.

## Patch Contract

When an outer loop invokes a coding agent, the loop owns:

- prepare and patch application,
- snapshot discovery and validation,
- checkpoint restore,
- build/relink,
- evaluator execution,
- scoring and accept/reject.

The coding agent owns one bounded source patch, then stops.

Preferred target surface for framework work:

- `tools/OpenROAD/src/dpl_evolve/src/EvolveLegalizer.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/EvolveLegalizer.h`
- `tools/OpenROAD/src/dpl_evolve/src/EvolveContext.h`
- `tools/OpenROAD/src/dpl_evolve/src/EvolveTelemetry.h`
- `tools/OpenROAD/src/dpl_evolve/src/StudentAlgorithm.cpp`
- LEGALM-stage files under `tools/OpenROAD/src/dpl_evolve/src/Legalm*.{h,cpp}`
- detailed-improvement files under
  `tools/OpenROAD/src/dpl_evolve/src/optimization/` and
  `tools/OpenROAD/src/dpl_evolve/src/objective/`
- `tools/OpenROAD/src/dpl_evolve/src/Optdp.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/OptMirror.cpp`
- existing donor files under `tools/OpenROAD/src/dpl_evolve/src/` when a stage
  intentionally borrows diamond, negotiation, or DRC logic.

Do not edit classic `tools/OpenROAD/src/dpl/`.  Do not edit evaluator/scoring
logic to make a result look better.

## Algorithm Standard

Bounded does not mean timid.  Real patches should change a mechanism:

- candidate generation or ordering,
- relaxed/differentiable guidance,
- row or cluster assignment,
- legality recovery,
- objective/proxy cost,
- repair trigger policy,
- bounded polish,
- telemetry that explains success or failure.

Weak patches that only tune constants are calibration probes, not algorithmic
results.

## High-Performance Interface Contract

The evolved framework boundary is in-process and control-plane only.
`EvolveContext` should carry small options such as thread budget, displacement
limits, and report names.  Do not move per-cell/per-net hot data through JSON,
string-keyed maps, cross-process calls, or generic callback dispatch.

Student implementations should keep hot data as compact C++ structures:
node-id keyed vectors, struct-of-arrays where useful, row/segment interval
indexes, bounded candidate arrays, and deterministic per-thread scratch
buffers.  Coarse donor hooks may be used to call a whole stage, but not inside
inner candidate loops.

Every algorithmic patch should state:

- mechanism changed,
- stage touched,
- expected HPWL/runtime/displacement/legality effect,
- expected failure mode,
- repair or failure-handling policy inside the algorithm.

Use `knowledge/EVIDENCE_POLICY.md` when converting run results or paper notes
into prompt text. Do not encode a single-case observation as a permanent
algorithm rule without marking its scope.

## Baselines

The canonical baseline/evolve lines live in `baseline/canonical_lines.yaml`.

Current OpenROAD DPL baseline intentionally mirrors the normal detail-place
flow:

```text
detailed_placement
improve_placement
optimize_mirroring
```

The evolved line mirrors that shape through the evolved command namespace:

```text
detailed_placement_evolve
improve_placement_evolve
optimize_mirroring_evolve
```

## Build And Run Rules

Build common OpenROAD once, then relink private variants:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" 10
"$DPL_EVOLVE_AGENT_ROOT/scripts/create_variant_start.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>" \
  --dpl-src /abs/path/to/variant/dpl_evolve
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>" \
  --dpl-src /abs/path/to/variant/dpl_evolve
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>" \
  --dpl-src /abs/path/to/variant/dpl_evolve \
  --threads 10
```

Variant/evolved runs must pass an explicit private binary.  Do not assume the
root `tools/install/OpenROAD/bin/openroad` is the candidate binary.

The Teacher/Student loop uses this relink path for algorithm experiments.  Do
not introduce shared-object runtime entrypoints unless the repository direction
explicitly changes again.

Strict evaluator output lives under:

```text
flow/reports/<platform>/<design>/<FLOW_VARIANT>/dpl_evolve_baseline/<run_tag>/metrics.json
```

The canonical HPWL field is `hpwl`, sourced from OpenROAD/DPL pin-based log
reports.  `hpwl_proxy` is a legacy cell-bbox diagnostic and must not be used
for promotion, Teacher planning, or public result tables.

Hard failures:

- build failure,
- evaluator failure,
- legality failure,
- missing/malformed metrics,
- uncontrolled displacement/runtime regression.

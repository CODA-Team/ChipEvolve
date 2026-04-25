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
framework.  The evolved command entrypoint is always:

```text
detailed_placement_evolve
```

Do not revive the old family-tree router unless explicitly assigned.  The old
family-flow notes, matrices, routers, and robustness reports were moved to
`local_backups/legacy_family_flow_cleanup_20260425/` so they do not pollute
default agent context.

The current source patch is:

```text
patches/openroad_dpl_evolve_framework.patch
```

It introduces the `EvolveLegalizer` stage skeleton behind
`detailed_placement_evolve`:

1. relaxed or differentiable-style guidance,
2. row or cluster assignment donor stage,
3. diamond-compatible legalization,
4. negotiation/repair only if needed,
5. bounded polish,
6. telemetry.

This order is a scaffold, not a final algorithm. Agents may replace, skip, or
reorder stages when a patch states the hypothesis and the evaluator checks the
result. Default behavior should stay close to diamond search until a later
patch proves that a stage replacement is better.

The framework also exposes a first lightweight plugin ABI:

```text
tools/OpenROAD/src/dpl_evolve/src/EvolvePluginApi.h
plugins/dpl_evolve_plugin_v1/
```

If `DPL_EVOLVE_PLUGIN_SO` points at a shared object exporting
`dpl_evolve_run_v1`, the prepared OpenROAD binary loads it at runtime.  This
lets agents test top-level stage policies by compiling only a small `.so`
instead of relinking OpenROAD for every idea.  The V1 plugin API exposes stage
callbacks and telemetry metrics only; deeper placement data APIs should be
added as an explicit new ABI version.

## Reference Sources

Use the compact donor shelf, not historical experiment directories:

```text
family_variants/reference_sources/
family_variants/REFERENCE_INDEX.yaml
```

Canonical donors:

- OpenROAD diamond DPL: current strict-track comparison anchor and local search
  donor, not a universal optimum claim.
- OpenROAD negotiation/NBLG: repair and overflow donor; do not assume it is the
  right primary engine for every case.
- `family_variants/negotiation_parallel_frontier/`: selected negotiation
  history donor; it supersedes old r5 records.
- LEGALM: staged relaxed legalization / ALM donor.
- DREAMPlace Abacus: row assignment and compaction donor.

If you need old algobank/family evidence, explicitly opt in to the ignored
backup directory.  Do not broad-read it by default.

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
- `tools/OpenROAD/src/dpl_evolve/src/EvolvePluginApi.h` only when extending
  the plugin ABI deliberately.
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

Every algorithmic patch should state:

- mechanism changed,
- stage touched,
- expected HPWL/runtime/displacement/legality effect,
- expected failure mode,
- rollback condition.

Use `knowledge/EVIDENCE_POLICY.md` when converting run results or paper notes
into prompt text. Do not encode a single-case observation as a permanent
algorithm rule without marking its scope.

## Baselines

The canonical baseline/evolve lines live in `baseline/canonical_lines.yaml`.

Current OpenROAD DPL baseline is intentionally two-stage:

```text
detailed_placement
detailed_placement -use_negotiation
```

This matches a practical legalization flow better than using negotiation alone.
The evolved line remains clean `detailed_placement_evolve`.

## Build And Run Rules

Build common OpenROAD once, then relink private variants:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" 10
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

For top-level orchestration experiments, agents may instead build a V1 plugin:

```bash
"$DPL_EVOLVE_AGENT_ROOT/plugins/dpl_evolve_plugin_v1/build.sh" \
  --openroad-src "$ORFS_ROOT/tools/OpenROAD" \
  --out "${DPL_EVOLVE_STATE_ROOT}/plugins/<agent_id>/libdpl_evolve_plugin.so"

DPL_EVOLVE_PLUGIN_SO="${DPL_EVOLVE_STATE_ROOT}/plugins/<agent_id>/libdpl_evolve_plugin.so" \
  "$DPL_EVOLVE_AGENT_ROOT/scripts/run_canonical_line.sh" ...
```

Use the plugin path for stage-order experiments; use private relink when the
actual C++ legalizer implementation changes.

Strict evaluator output lives under:

```text
flow/reports/<platform>/<design>/<FLOW_VARIANT>/dpl_evolve_baseline/<run_tag>/metrics.json
```

Hard failures:

- build failure,
- evaluator failure,
- legality failure,
- missing/malformed metrics,
- uncontrolled displacement/runtime regression.

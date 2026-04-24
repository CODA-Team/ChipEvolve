# AGENTS.md

This file is for Codex/agent execution. For human setup and quick start, use
`README.md`.

This repo is the standalone control plane for `dpl_evolve`. It is not an ORFS
submodule and should not be treated as one.

## Runtime Roots

Every script resolves runtime through these roots:

- `DPL_EVOLVE_AGENT_ROOT`: this repo.
- `ORFS_ROOT`: the external OpenROAD-flow-scripts workspace.
- `DPL_EVOLVE_STATE_ROOT`: mutable runtime state, builds, checkpoints, packets,
  operations, and variant binaries.

Machine-local values belong in untracked `env.sh`, using `env.sh.example` as
the template. Do not hardcode local paths in tracked scripts or docs.

Optional convenience only:

- `$DPL_EVOLVE_AGENT_ROOT/.mounted_orfs`

Do not introduce another runtime model.

## Loop-Driven Patch Contract

When an outer Python loop invokes Codex, the loop already owns:

- prepare and patch application
- flow variant discovery
- snapshot validation
- checkpoint restore
- build
- evaluator execution
- scoring and accept/reject

Codex owns only one thing:

- make one bounded source patch, then stop

## Minimal Read Set

For a bounded patch turn, read only:

- `$DPL_EVOLVE_PACKET_DIR/current_run_packet.md`
- `$DPL_EVOLVE_AGENT_ROOT/skills/patch_rules.md`
- the active `problem.yaml`
- the one target source file named by the packet

Patch after those focused reads. Do not start with a repo survey.
Do not use `README.md` as bounded-patch context.

## Do Not Read During A Bounded Patch

- `tasks/archive/*`
- `knowledge/stage_context/*`
- `knowledge/delta_ledger/*`
- `knowledge/design_profiles/*`
- `flow/Makefile`
- `flow/scripts/*`
- `flow/designs/*/config.mk`
- git history
- broad repo status

Those paths are for flow debugging or project maintenance, not for normal
code-evolve turns.

## Patch Surface

Preferred target files:

- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizerPass.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.h`
- `tools/OpenROAD/src/dpl_evolve/src/Opendp.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/Opendp.tcl`

Do not edit classic `tools/OpenROAD/src/dpl/` for this project.

Family-specific implementations, such as LEGALM, must live in materialized
variant source trees. Do not reintroduce them into the clean main
`dpl_evolve` base.

## Binary Rule

Clean runs may use the root OpenROAD binary.

Variant/family runs must use an explicit private binary:

```bash
source "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>/variant_env.sh"
python3 "$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/evaluator.py" \
  --openroad-binary "${OPENROAD_BINARY}" ...
```

Never assume `tools/install/OpenROAD/bin/openroad` is correct inside a variant
loop.

## Build Model

Preferred path:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" 8
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>" \
  --dpl-src /abs/path/to/variant/dpl_evolve
source "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>/variant_env.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh" --threads 8
```

This rebuilds only variant-owned `dpl_evolve` objects, relinks a private
`openroad`, and symlinks common-core `sta` when available.

## Evaluation Rule

Use strict legalization-only first. The reusable snapshot must already exist:

```text
flow/results/<platform>/<design>/<FLOW_VARIANT>/3_4_place_resized.odb
```

The baseline wrapper reuses that snapshot. It should not rebuild upstream
Yosys/place during strict evaluator runs.

Primary result:

```text
flow/reports/<platform>/<design>/<FLOW_VARIANT>/dpl_evolve_baseline/<run_tag>/metrics.json
```

Hard failures:

- build failure
- evaluator failure
- legality failure
- missing or malformed `metrics.json`
- uncontrolled displacement/runtime regression

# AGENTS.md

This file is the short operating contract for Codex inside `evolve_agent`.

This directory is the only intended control-plane tree in the repo. Keep the
agent surface narrow and decoupled from the target plane.

Runtime is now resolved through three explicit roots:

- `ORFS_ROOT`
- `DPL_EVOLVE_AGENT_ROOT`
- `DPL_EVOLVE_STATE_ROOT`

The target direction is documented in:

- `$DPL_EVOLVE_AGENT_ROOT/knowledge/plans/common_core_variant_relink.md`

Do not assume the control repo is registered as a git submodule inside ORFS.
Use the explicit roots above.

An optional ignored mount is supported at:

- `$DPL_EVOLVE_AGENT_ROOT/.mounted_orfs`

That mount is a convenience, not a second runtime model.

## Role

Codex is a bounded patcher.

- patch code in `tools/OpenROAD/src/dpl_evolve/`
- call the existing baseline runners
- decide using `metrics.json`

Codex is not the scheduler, not the knowledge store, and not a replacement for
the baseline harness.

## Default loop behavior

When Codex is invoked by the automated evolve loop, assume the outer loop has
already done these checks:

- selected a valid `FLOW_VARIANT`
- verified `3_4_place_resized.odb` exists
- refreshed `knowledge/packets/current_run_packet.*`
- chosen the evaluator line and run tag
- taken care of build, evaluator, scoring, and checkpoint ownership

For those loop-driven turns, the minimum read set is:

1. `knowledge/packets/current_run_packet.md`
2. `skills/patch_rules.md`
3. the current `problem.yaml`
4. the target-plane file you plan to patch

Do not expand the read set unless you are blocked.
Do not open `tasks/archive/*`, `knowledge/stage_context/*`,
`knowledge/delta_ledger/*`, `knowledge/design_profiles/*`, or repo-wide
README files during a bounded patch turn if the packet already gives you the
needed fact.
Do not inspect git history or broad repo status during a bounded patch turn
unless the task explicitly asks for flow debugging.

## Research budget

For a bounded patch turn, patch after a few focused reads.

Do not spend time re-deriving:

- whether the reusable place snapshot exists
- how the outer loop will build or evaluate
- whether `config.mk` or `flow/Makefile` might retrigger place
- broad flow defaults already summarized in the current packet

If the packet and prompt already provide a fact, treat it as authoritative for
that attempt.

Patch after one target-file read whenever possible. Do not perform a broad repo
survey before the first bounded edit.

## Boundaries

- Target plane: `tools/OpenROAD/src/dpl_evolve/`
- Artifact plane: `flow/`
- Control plane: `DPL_EVOLVE_AGENT_ROOT/`
- Optional external runtime reference: upstream `science-codeevolve`, but it is
  not required to exist inside this repo tree

Do not mix those planes.

For loop-driven bounded patch turns:

- target plane is the normal read/write surface
- control plane is read-only unless the task explicitly asks to fix the flow
- artifact plane is read-only and usually should not be inspected at all

## Binary rules

- Clean baseline and clean evolve runs may use the root OpenROAD binary.
- Family-variant runs must use a dedicated variant binary.
- Preferred pattern:
  - `scripts/configure_openroad_core.sh`
  - `scripts/build_openroad_core.sh`
  - `scripts/configure_openroad_variant_relink.sh`
  - `source <variant-root>/variant_env.sh`
  - `scripts/build_openroad_variant_relink.sh`
  - `scripts/run_canonical_line.sh --openroad-binary "${OPENROAD_BINARY}" ...`
- Fallback full-variant pattern:
  - `scripts/configure_openroad_variant.sh`
  - `source <variant-root>/variant_env.sh`
  - `scripts/build_openroad_only.sh`
- Do not assume `tools/install/OpenROAD/bin/openroad` is correct once you are
  inside a family-variant loop.

## Current patch surface

Allowed first:

- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizerPass.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.h`
- `tools/OpenROAD/src/dpl_evolve/src/Opendp.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/Opendp.tcl`

Variant-only:

- `$DPL_EVOLVE_AGENT_ROOT/family_variants/legalm_engine/`
- materialized source trees created with `scripts/materialize_family_variant.sh`

For `LEGALM` work, materialize the `legalm_engine` family into its own
`dpl_evolve` source tree and patch that variant source. Do not reintroduce the
family implementation into `tools/OpenROAD/src/dpl_evolve/`.

Read-only unless a task expands scope:

- `tools/OpenROAD/src/dpl_evolve/src/Optdp.cpp`
- `flow/scripts/*`
- unrelated OpenROAD tools

Do not edit `flow/designs/*/config.mk` during a bounded patch turn unless the
task explicitly asks for artifact-plane tuning.

## Evaluation policy

Prefer the strict legalizer track first.

Use reduced-flow runs only after strict-track behavior looks promising.
Judge candidates from structured outputs, not from log impressions.

Use `python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/checkpoint.py"` for any state you may need to
come back to. The checkpoint store is local-only and ignored by git.

Hard failures:

- build failure
- runner failure
- legality failure
- missing or malformed `metrics.json`
- large uncontrolled displacement growth
- runaway runtime

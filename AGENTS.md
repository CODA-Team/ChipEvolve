# AGENTS.md

This file is the short operating contract for Codex inside `evolve_agent`.
For the full repo map, read `README.md` first, then `SCRIPT_MAP.md`.
For the repo-local execution skills, read `skills/README.md` next.

This directory is the only intended control-plane tree in the repo. Keep the
agent surface narrow and decoupled from the target plane.

All build/run commands assume this repo is mounted as `evolve_agent/` inside an
ORFS workspace. Do not treat the standalone authoring checkout as the runtime
workspace unless it also contains sibling `flow/` and `tools/OpenROAD/`.

## Role

Codex is a bounded patcher.

- patch code in `tools/OpenROAD/src/dpl_evolve/`
- call the existing baseline runners
- decide using `metrics.json`

Codex is not the scheduler, not the knowledge store, and not a replacement for
the baseline harness.

## Minimal operating order

1. Read the current packet in `knowledge/packets/`.
2. Read `skills/README.md`.
3. Read `skills/patch_rules.md`.
4. Create or refresh a local checkpoint with `scripts/checkpoint.py`.
5. Patch only approved target-plane files.
6. Review the implementation for obvious efficiency issues before adding more patch logic.
7. For family work, configure a dedicated variant root and source its `variant_env.sh`.
8. Build through the variant-aware OpenROAD-only path.
9. Run one canonical baseline/evolve line or the suite through the existing wrappers.
10. For any `--family-variant` run, pass an explicit OpenROAD binary.
11. For a new case, classify the baseline result first with `scripts/recommend_initial_family.py`.
12. Compare runs with `scripts/compare_runs.py`, then read evaluator output and `metrics.json`.
13. Keep, revise, or restore through checkpoints.

## Boundaries

- Target plane: `tools/OpenROAD/src/dpl_evolve/`
- Artifact plane: `flow/`
- Control plane: `evolve_agent/`
- Optional external runtime reference: upstream `science-codeevolve`, but it is
  not required to exist inside this repo tree

Do not mix those planes.

## Binary rules

- Clean baseline and clean evolve runs may use the root OpenROAD binary.
- Family-variant runs must use a dedicated variant binary.
- Preferred pattern:
  - `scripts/configure_openroad_variant.sh`
  - `source <variant-root>/variant_env.sh`
  - `scripts/build_openroad_only.sh`
  - `scripts/run_canonical_line.sh --openroad-binary "${OPENROAD_BINARY}" ...`
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

- `evolve_agent/family_variants/legalm_engine/`
- materialized source trees created with `scripts/materialize_family_variant.sh`

For `LEGALM` work, materialize the `legalm_engine` family into its own
`dpl_evolve` source tree and patch that variant source. Do not reintroduce the
family implementation into `tools/OpenROAD/src/dpl_evolve/`.

Read-only unless a task expands scope:

- `tools/OpenROAD/src/dpl_evolve/src/Optdp.cpp`
- `flow/scripts/*`
- unrelated OpenROAD tools

## Evaluation policy

Prefer the strict legalizer track first.

Use reduced-flow runs only after strict-track behavior looks promising.
Judge candidates from structured outputs, not from log impressions.

Use `python3 evolve_agent/scripts/checkpoint.py` for any state you may need to
come back to. The checkpoint store is local-only and ignored by git.

Hard failures:

- build failure
- runner failure
- legality failure
- missing or malformed `metrics.json`
- large uncontrolled displacement growth
- runaway runtime

Current large-case policy:

- prefer `ariane133`, `jpeg`, `ibex`, `aes`, `ethmac` as interactive stress cases
- do not use macro-heavy `bp_quad` for interactive family iteration once smaller
  large cases already show runtime divergence
- for large cases, reject families that only improve HPWL but blow up runtime
  without a clear timing benefit

## Required reads before patching

- `README.md`
- `baseline/canonical_lines.yaml`
- `knowledge/stage_context/detail_place_stack.yaml`
- `knowledge/delta_ledger/nblg_to_openroad.yaml`
- `knowledge/delta_ledger/legalm_to_openroad.yaml`
- `knowledge/family_components/effective_families.yaml`
- current packet in `knowledge/packets/`

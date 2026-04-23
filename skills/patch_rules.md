# Skill: patch_rules

## Principle
Codex edits **only the bounded legalizer surfaces** unless a task explicitly expands the surface.

## Early-phase allowed surfaces
- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizerPass.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.h`
- `tools/OpenROAD/src/dpl_evolve/src/Opendp.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/Opendp.tcl`

## Family variants

- `LEGALM` is a family-specific variant, not part of the clean initial evolve base.
- Materialize it with `evolve_agent/scripts/materialize_family_variant.sh`.
- Patch the materialized variant source tree, not `tools/OpenROAD/src/dpl_evolve/`.

## Read-only unless task expands scope
- `tools/OpenROAD/src/dpl_evolve/src/Optdp.cpp`
- ORFS `flow/scripts/*`
- unrelated OpenROAD tools

For loop-driven bounded patch turns, do not inspect or edit `flow/Makefile`,
`flow/designs/*/config.mk`, or other artifact-plane files unless the task
explicitly asks for runner/config changes.

## Patch style
- make small, mechanism-specific edits
- allow stacked family evolution, but each patch note must still name the newly
  added mechanism layer
- preserve existing interfaces unless the task explicitly allows interface change
- if a Tcl option is added, update both Tcl wrapper and the receiving C++ layer
- review the implementation for obvious low-value overheads before promoting a
  family on large cases

## Preferred mechanism families
- main-pass objective shaping
- stuck-cell escape / local-optimum escape
- selective refinement and recovery
- localized swap / localized postopt
- LEGALM Stage1 / Stage2 / Stage3 improvement
- runtime-aware implementation review

## Required patch note
For each patch, record:
- touched files
- mechanism name
- why this mechanism matches the current packet
- expected metric effect
- rollback condition

## Forbidden behaviors
- large speculative rewrites
- simultaneous evaluator + algorithm edits
- moving files between target plane and control plane
- adding third-party code directly into target plane without explicit task approval
- re-integrating family-specific legalizers into the clean main-tree base
- claiming a family is promoted without comparing against a baseline or previous
  family with `scripts/compare_runs.py`

# CODEX TASK 02 — First bounded legalizer patch cycle

## Goal
Produce one small, mechanism-specific patch on the negotiation legalizer and evaluate it on the strict legalizer track.

## Preconditions
Task 01 is complete.

## Allowed patch surfaces
- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/Opendp.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/Opendp.tcl`

Prefer the first file only unless interface exposure is required.

## Required reading
Before editing, read:
- `knowledge/packets/current_run_packet.md`
- `skills/patch_rules.md`
- `knowledge/delta_ledger/nblg_to_openroad.yaml`
- `knowledge/delta_ledger/docs_vs_current_code.yaml`

## Patch policy
- one mechanism family only
- no unrelated refactor
- no control-plane edits in the same patch
- keep a rollback path

## Recommended first mechanisms
Choose one:
1. negotiation cost rebalance
2. adaptive penalty schedule tweak
3. small post-negotiation refinement hook restoration

## Procedure
1. Write a patch note first.
2. Apply the bounded patch.
3. Build OpenROAD.
4. Run strict-track single baseline on evolve line.
5. Read `metrics.json`.
6. Compare against the nearest baseline.
7. Decide keep / revert.

## Acceptance criteria
A first patch cycle is complete only if:
- build succeeds
- strict-track run completes
- legality passes
- evaluator JSON is written
- keep/revert decision is recorded

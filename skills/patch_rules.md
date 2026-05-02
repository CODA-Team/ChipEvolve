# Skill: patch_rules

## Principle

Codex edits only the bounded `dpl_evolve` framework surface unless a task
explicitly expands the scope.

## Preferred Surfaces

- `tools/OpenROAD/src/dpl_evolve/src/EvolveLegalizer.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/EvolveLegalizer.h`
- `tools/OpenROAD/src/dpl_evolve/src/EvolveContext.h`
- `tools/OpenROAD/src/dpl_evolve/src/EvolveTelemetry.h`
- `tools/OpenROAD/src/dpl_evolve/src/StudentAlgorithm.cpp`
- LEGALM-stage files under `tools/OpenROAD/src/dpl_evolve/src/Legalm*.{h,cpp}`
- detailed-improvement and objective files under
  `tools/OpenROAD/src/dpl_evolve/src/optimization/` and
  `tools/OpenROAD/src/dpl_evolve/src/objective/`
- `tools/OpenROAD/src/dpl_evolve/src/Optdp.cpp`
- existing `tools/OpenROAD/src/dpl_evolve/src/Place.cpp` or
  `NegotiationLegalizer*` files only when borrowing a specific donor mechanism.

Do not edit classic `tools/OpenROAD/src/dpl/`.

## Reference Inputs

Read compact references before patching:

- `family_variants/REFERENCE_INDEX.yaml`
- one donor under `family_variants/`
- `family_variants/openroad_negotiation_nblg/mechanism_deltas/`
  only if assigned to negotiation-history mechanisms

Do not broad-read external archives or ignored local backups unless the task
explicitly asks for old family-flow evidence.

## Patch Style

- Change one coherent mechanism at a time.  For Teacher/Student rounds, that
  mechanism may span legalization/detailed placement, improve placement, and
  their shared objective/handoff.
- Keep `detailed_placement_evolve` as the primary evolved placement command.
- Keep evaluator, scoring, and ORFS flow scripts locked.
- If a Tcl option is added, update both the Tcl wrapper and C++ receiver.
- Add telemetry when a new stage or repair operator executes.

## Required Patch Note

For each patch, record:

- touched files,
- stage or mechanism name,
- expected HPWL/runtime/displacement/legality effect,
- expected failure mode,
- repair or failure-handling policy inside the algorithm.

## Forbidden Behaviors

- simultaneous evaluator and algorithm edits,
- moving target-plane code into the control plane,
- adding third-party source directly into target code without explicit approval,
- claiming success without comparing against the current baseline,
- using fallback-to-default behavior as evidence of algorithm quality.

# LEGALM-Guidance Source Reference

This directory preserves a measured `detailed_placement_evolve`
LEGALM-style guidance implementation as a source-code reference for student
agents.

It is a reference donor, not a separate active family or alternate entrypoint.
The evolved command remains `detailed_placement_evolve`; future agents should
study this code, then port or replace bounded mechanisms in the live
`tools/OpenROAD/src/dpl_evolve/src` implementation.

## Contents

- `source/DifferentialGuidance.cpp`: staged CPU guidance implementation.
- `source/EvolveLegalizer.cpp`: top-level evolve legalizer orchestration.
- `source/EvolveLegalizer.h`: public evolve legalizer interface.
- `source/EvolveContext.h`: shared context wrapper.
- `source/EvolveTelemetry.h`: lightweight stage telemetry structures.

## How Students Should Use This

- Treat this as a concrete implementation baseline for Stage A guidance,
  ALM/BGD-inspired repair, Stage3 no-overflow refinement, and per-stage
  telemetry.
- Do not assume every constant or stage choice is final. The algorithmic flow
  is intentionally evolvable.
- Compare any new idea against Diamond and active evolve metrics for the
  active case.
- If a new implementation diverges, explain which mechanism was preserved,
  replaced, or removed.

## Known Calibration

This snapshot is useful because it has compiled and run with JPEG-class
validation. It is not proof of optimality.
Recent evidence showed it can be legal and fast enough on JPEG, but BP_QUAD
still exposes large-case overhead where Stage A may do no useful guided starts.

Students should therefore view this as a strong implementation reference, not
as a locked design.

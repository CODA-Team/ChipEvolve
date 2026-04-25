# OpenROAD Negotiation / NBLG Reference

Role: overflow repair, stuck-cell recovery, history-cost donor, and
negotiation-style final legalization stage.

The durable source-of-truth is the prepared OpenROAD `dpl_evolve` base produced
by `patches/openroad_dpl_evolve_base.patch`.  Key files inside the materialized
source tree are:

- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.h`
- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizerPass.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/Opendp.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/Opendp.tcl`

Use this reference for bounded repair ideas, not as the default quality
baseline.  Prior runs showed that negotiation can be useful as a repair
operator, but it is not automatically better than diamond search on normal
strict detailed-placement cases.

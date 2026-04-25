# OpenROAD Negotiation / NBLG Reference

Role: overflow repair, stuck-cell recovery, history-cost donor, and
negotiation-style final legalization stage.

This directory keeps a compact source snapshot from OpenROAD classic DPL:

- `source/src/NegotiationLegalizer.cpp`
- `source/src/NegotiationLegalizer.h`
- `source/src/NegotiationLegalizerPass.cpp`
- `source/src/Opendp.cpp`
- `source/src/Opendp.tcl`
- `source/include/dpl/Opendp.h`

Use this reference for bounded repair ideas, not as the default quality
baseline.  Prior runs showed that negotiation can be useful as a repair
operator, but it is not automatically better than diamond search on normal
strict detailed-placement cases.

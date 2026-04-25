# OpenROAD Diamond DPL Reference

Role: current strict-track comparison anchor and diamond-compatible donor.

This directory keeps a compact source snapshot from OpenROAD classic DPL:

- `source/src/Place.cpp`
- `source/src/Opendp.cpp`
- `source/src/PlacementDRC.cpp`
- `source/src/PlacementDRC.h`
- `source/include/dpl/Opendp.h`

Study this path when optimizing local candidate search, row/site legality,
placement DRC checks, rip-up behavior, and diamond-compatible fallback.  Local
strict-track runs currently make this the comparison anchor; that is an
experiment baseline, not a claim that diamond is universally optimal.  New
framework stages should stay comparable to this path until a case-specific
improvement is measured.

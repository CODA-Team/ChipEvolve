# OpenROAD Diamond DPL Reference

Role: primary baseline and diamond-compatible donor.

This directory keeps a compact source snapshot from OpenROAD classic DPL:

- `source/src/Place.cpp`
- `source/src/Opendp.cpp`
- `source/src/PlacementDRC.cpp`
- `source/src/PlacementDRC.h`
- `source/include/dpl/Opendp.h`

Study this path when optimizing local candidate search, row/site legality,
placement DRC checks, rip-up behavior, and diamond-compatible fallback.  It is
currently the strongest baseline on the strict detailed-placement smoke cases,
so new framework stages should default to behavior close to this path until a
case-specific improvement is proven.

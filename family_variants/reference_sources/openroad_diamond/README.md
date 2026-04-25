# OpenROAD Diamond DPL Reference

Role: primary baseline and diamond-compatible donor.

The durable source-of-truth is the prepared OpenROAD `dpl_evolve` base produced
by `patches/openroad_dpl_evolve_base.patch`.  Key files inside the materialized
source tree are:

- `tools/OpenROAD/src/dpl_evolve/src/Place.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/Opendp.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/PlacementDRC.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/PlacementDRC.h`
- `tools/OpenROAD/src/dpl_evolve/include/dpl_evolve/Opendp.h`

Study this path when optimizing local candidate search, row/site legality,
placement DRC checks, rip-up behavior, and diamond-compatible fallback.  It is
currently the strongest baseline on the strict detailed-placement smoke cases,
so new framework stages should default to behavior close to this path until a
case-specific improvement is proven.

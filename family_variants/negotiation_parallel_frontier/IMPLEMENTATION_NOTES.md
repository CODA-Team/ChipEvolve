# Implementation Notes

This is the selected negotiation-history donor.  It supersedes the older r5
records in default context because the threaded frontier path is the only
historical negotiation line worth keeping visible.

Mechanisms to reuse selectively:

- worker-thread support for row-disjoint history updates,
- parallel precompute of negotiation-order sort keys,
- serial grid mutation for safety,
- true two-pass candidate frontier design,
- candidate telemetry for cap hits, rejected DRC, no-valid, collected, and
  scored frontier candidates.

Do not revive the old matrix generator by default.  If a child agent needs one
of these mechanisms, port it into an `EvolveLegalizer` stage patch and evaluate
through the normal `detailed_placement_evolve` command.

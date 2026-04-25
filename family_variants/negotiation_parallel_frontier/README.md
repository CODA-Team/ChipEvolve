# Negotiation Parallel Frontier Reference

Role: selected negotiation-history donor.

This record replaces the older r5/r6 naming in default agent context.  The old
r5 record was moved to `local_backups/legacy_family_flow_cleanup_20260425/`
because the faster threaded frontier path is the only negotiation variant worth
keeping visible by default.

Keep this directory as reference material, not as the active framework
entrypoint.  New work should port useful mechanisms into the constrained
`EvolveLegalizer` framework behind `detailed_placement_evolve`.

Useful mechanisms preserved here:

- command-level OpenROAD `-threads` is passed into `dpl_evolve`;
- row-disjoint history-cost updates can use worker threads;
- negotiation-order sort keys are precomputed in parallel before serial sort;
- grid-mutating `ripUp`, `place`, and DRC-sensitive candidate search stay
  serial;
- two-pass frontier design: collect bounded cheap candidates first, then apply
  net-anchor quality scoring only to the retained frontier;
- `FindBestStats` style candidate telemetry for candidate caps, no-valid
  searches, and frontier pruning.

Patch artifact:

```text
research_patches/negotiation_parallel_frontier.patch
```

Do not read old r5 docs unless explicitly debugging historical experiments.

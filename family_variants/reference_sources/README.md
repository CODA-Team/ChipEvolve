# Algorithm Source References

This directory is the compact source-code reading shelf for future
`detailed_placement_evolve` agents.  These records are references, not active
families.  They give agents concrete implementations to study while keeping the
main evolve entrypoint clean and patch-based.

## Rules

- The only evolved command remains `detailed_placement_evolve`.
- Reference sources must not be selected as flow parents by default.
- Durable implementation changes should still be delivered as patches under
  `patches/` or as explicitly materialized variant recipes.
- Runtime experiments belong under `DPL_EVOLVE_STATE_ROOT`, not in this
  directory.

## References

- `openroad_diamond/`: OpenROAD's diamond-search detailed placement baseline.
- `openroad_negotiation_nblg/`: OpenROAD negotiation legalizer / NBLG-style
  repair donor.
- `../negotiation_parallel_frontier/`: selected negotiation-history donor that
  supersedes old r5/r6 naming.
- `legalm/`: LEGALM sidecar lineage and ALM-style staged legalization donor.
- `legalm_cpu_reference/`: handoff packet for an external high-performance CPU
  LEGALM implementation; includes data structures and a ready-to-send prompt,
  not an OpenROAD plugin or active family recipe.
- `dreamplace_abacus/`: compact DREAMPlace Abacus legalization source snapshot.

Use these references to design stages, objectives, and repair operators for the
new constrained top-level framework.  Do not resurrect the old family-tree
router unless a task explicitly asks for legacy comparison.

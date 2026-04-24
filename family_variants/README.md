# Family Variants

This directory stores reusable family-specific `dpl_evolve` source variants.

The model is:

- `tools/OpenROAD/src/dpl_evolve` is the clean initial evolve base
- each family variant is a patch over that base
- a materialized variant source tree is built into its own OpenROAD binary

Use:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/materialize_family_variant.sh" \
  --family legalm_engine \
  --output-dir "$DPL_EVOLVE_STATE_ROOT/family_variants/legalm_engine/dpl_evolve" \
  --force
```

Then build that source tree with the lightweight relink path:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "$DPL_EVOLVE_STATE_ROOT/variants/legalm_engine" \
  --dpl-src "$DPL_EVOLVE_STATE_ROOT/family_variants/legalm_engine/dpl_evolve"

source "$DPL_EVOLVE_STATE_ROOT/variants/legalm_engine/variant_env.sh"

"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh" --threads 10
```

Run family variants with an explicit binary. Do not rely on the root
`tools/install/OpenROAD/bin/openroad` once a family variant is involved.

Active families:

- `legalm_engine/`

# Family Variants

This directory stores reusable family-specific `dpl_evolve` source variants.

The model is:

- `tools/OpenROAD/src/dpl_evolve` is the clean initial evolve base
- each family variant is a patch over that base
- a materialized variant source tree is built into its own OpenROAD binary

Use:

```bash
./evolve_agent/scripts/materialize_family_variant.sh \
  --family legalm_engine \
  --output-dir ./.codex_state/family_variants/legalm_engine/dpl_evolve \
  --force
```

Then build that source tree as an OpenROAD variant:

```bash
./evolve_agent/scripts/configure_openroad_variant.sh \
  --variant-root ./.codex_state/openroad_variants/legalm_engine \
  --dpl-src ./.codex_state/family_variants/legalm_engine/dpl_evolve
```

Active families:

- `legalm_engine/`

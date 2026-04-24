# legalm_engine

`legalm_engine` is a family-specific `dpl_evolve` variant.

It is not part of the clean initial evolve base. Materialize it into its own
source tree, build a dedicated OpenROAD binary, and run it through the strict
legalization-only evolve flow.

Materialize:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/materialize_family_variant.sh" \
  --family legalm_engine \
  --output-dir "$DPL_EVOLVE_STATE_ROOT/family_variants/legalm_engine/dpl_evolve" \
  --force
```

Configure and build:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "$DPL_EVOLVE_STATE_ROOT/variants/legalm_engine" \
  --dpl-src "$DPL_EVOLVE_STATE_ROOT/family_variants/legalm_engine/dpl_evolve"

source "$DPL_EVOLVE_STATE_ROOT/variants/legalm_engine/variant_env.sh"

"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh" --threads 8
```

Run:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/run_canonical_line.sh" \
  --line evolve_line \
  --family-variant legalm_engine \
  --openroad-binary "${OPENROAD_BINARY}" \
  --design-config ./designs/nangate45/gcd/config.mk \
  --flow-variant smoke_legalm_variant
```

The canonical family metadata lives in:

- `manifest.yaml`
- `../../knowledge/family_components/legalm_engine.yaml`

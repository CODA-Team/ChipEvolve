# legalm_engine

`legalm_engine` is a family-specific `dpl_evolve` variant.

It is not part of the clean initial evolve base. Materialize it into its own
source tree, build a dedicated OpenROAD binary, and run it through the strict
legalization-only evolve flow.

Materialize:

```bash
./evolve_agent/scripts/materialize_family_variant.sh \
  --family legalm_engine \
  --output-dir ./.codex_state/family_variants/legalm_engine/dpl_evolve \
  --force
```

Configure and build:

```bash
./evolve_agent/scripts/configure_openroad_variant.sh \
  --variant-root ./.codex_state/openroad_variants/legalm_engine \
  --dpl-src ./.codex_state/family_variants/legalm_engine/dpl_evolve

OPENROAD_BUILD_DIR=./.codex_state/openroad_variants/legalm_engine/build \
OPENROAD_INSTALL_ROOT=./.codex_state/openroad_variants/legalm_engine/install/OpenROAD \
OPENROAD_BINARY=./.codex_state/openroad_variants/legalm_engine/install/OpenROAD/bin/openroad \
./evolve_agent/scripts/build_openroad_only.sh 8
```

Run:

```bash
./evolve_agent/scripts/run_canonical_line.sh \
  --line evolve_line \
  --family-variant legalm_engine \
  --openroad-binary ./.codex_state/openroad_variants/legalm_engine/install/OpenROAD/bin/openroad \
  --design-config ./designs/nangate45/gcd/config.mk \
  --flow-variant smoke_legalm_variant
```

The canonical family metadata lives in:

- `manifest.yaml`
- `../../knowledge/family_components/legalm_engine.yaml`

# Skill: build_openroad

Use this when you are responsible for building binaries. Loop-driven patching
agents normally should not use it.

## Preconditions

- `DPL_EVOLVE_AGENT_ROOT`, `ORFS_ROOT`, and `DPL_EVOLVE_STATE_ROOT` are set.
- `ORFS_ROOT` has already been prepared.
- External tool dependencies are already available. Do not run
  `./build_openroad.sh --local` inside the evolve loop.

## Preferred Build Path

Build common core once:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" 8
```

Build a private variant binary:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>" \
  --dpl-src /abs/path/to/<agent_id>/dpl_evolve
source "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>/variant_env.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh" --threads 8
```

Expected outputs:

- `${OPENROAD_BINARY}`
- `${OPENROAD_INSTALL_ROOT}/bin/sta` as a symlink when common-core `sta` exists

## Fallback Only

Use this only if the relink path cannot express the change:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>" \
  --dpl-src /abs/path/to/<agent_id>/dpl_evolve
source "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>/variant_env.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_only.sh" 8
```

## Evidence To Report

- build status
- binary path
- elapsed build time
- first compiler error block if failed

## Do Not

- do not rebuild Yosys or the whole ORFS stack
- do not share one variant binary across different source variants
- do not assume root `tools/install/OpenROAD/bin/openroad` is correct for a
  family/variant run

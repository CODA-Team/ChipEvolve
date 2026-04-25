# Common-Core Variant Relink

This is the implemented build architecture for `dpl_evolve_agent`.

## Goal

After the first common-core OpenROAD build, each agent should rebuild only its
own `dpl_evolve` code and relink a private `openroad` binary.

No plugin runtime is needed. We use compile-time source variants.

## Roots

- `ORFS_ROOT`: external OpenROAD-flow-scripts workspace.
- `DPL_EVOLVE_AGENT_ROOT`: standalone control repo.
- `DPL_EVOLVE_STATE_ROOT`: mutable runtime cache.

If `ORFS_ROOT` contains spaces, scripts create a stable no-space symlink under
`DPL_EVOLVE_STATE_ROOT` and use that alias for CMake/make paths.

## Layout

```text
${DPL_EVOLVE_STATE_ROOT}/
  openroad_core/<openroad_sha>/
    build/
    install/OpenROAD/
  variants/<agent_id>/
    dpl_evolve/
    build/
    install/OpenROAD/bin/openroad
    install/OpenROAD/bin/sta -> common-core sta
    variant_env.sh
```

## Prepare Layer

`scripts/prepare_workspace.sh` applies only the minimal required patches:

- ORFS overlay, currently minimal.
- OpenROAD `src/dpl_evolve` clean base.

Classic `tools/OpenROAD/src/dpl/` stays upstream.

## Common-Core Layer

Run once per OpenROAD anchor/toolchain:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" 10
```

This produces the common build/link recipes and common binaries.

## Variant Layer

Each agent or family gets one private `dpl_evolve` tree:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>" \
  --dpl-src /abs/path/to/<agent_id>/dpl_evolve
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>" \
  --dpl-src /abs/path/to/<agent_id>/dpl_evolve \
  --threads 10
```

The build script:

- reads common-core compile/link recipes
- rebuilds variant-owned `dpl_evolve` objects
- relinks private `openroad`
- symlinks common-core `sta` when available

## Evaluation Layer

Variant runs must bind the private binary explicitly:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/evaluator.py" \
  --problem "$DPL_EVOLVE_AGENT_ROOT/problems/gcd_nangate45/problem.yaml" \
  --mode single \
  --line evolve_default \
  --flow-variant <FLOW_VARIANT> \
  --run-tag <RUN_TAG> \
  --skip-build \
  --openroad-binary "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>/install/OpenROAD/bin/openroad" \
  --out "${DPL_EVOLVE_STATE_ROOT}/checkpoints/operations/<RUN_TAG>/eval.json"
```

Strict evaluator runs reuse:

```text
flow/results/<platform>/<design>/<FLOW_VARIANT>/3_4_place_resized.odb
```

They should not rebuild upstream placement stages.

## Verified Smoke

On 2026-04-24, AES and IBEX were evaluated in parallel from the same common
core with two different private `openroad` binaries. Both runs completed with
`status=ok`.

This is the path agents should use unless a task explicitly asks for a heavier
full-variant build.

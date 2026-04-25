# DPL-Evolve Plugin V1

This is the lightweight top-level plugin carrier for
`detailed_placement_evolve`.

The prepared OpenROAD binary is linked once with the framework loader.  Later,
an agent can compile a small shared object and set:

```bash
export DPL_EVOLVE_PLUGIN_SO=/abs/path/to/libdpl_evolve_plugin.so
```

Then `detailed_placement_evolve` loads the plugin and calls
`dpl_evolve_run_v1`.  The first ABI exposes stage callbacks only:

- run diamond-compatible legalization,
- run negotiation repair,
- emit integer metrics.

This is enough to evolve top-level stage order without relinking OpenROAD.  It
is not yet a full cell-level placement API; deeper data/move APIs should be
added as a new ABI version when needed.

Build the example plugin:

```bash
./build.sh \
  --openroad-src "$ORFS_ROOT/tools/OpenROAD" \
  --out "$DPL_EVOLVE_STATE_ROOT/plugins/default_diamond/libdpl_evolve_plugin.so"
```

Run with an existing prepared OpenROAD binary:

```bash
DPL_EVOLVE_PLUGIN_SO="$DPL_EVOLVE_STATE_ROOT/plugins/default_diamond/libdpl_evolve_plugin.so" \
  "$OPENROAD_BINARY" ...
```

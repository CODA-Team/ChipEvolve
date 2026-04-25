# Plugins

This directory contains optional runtime-loaded DPL-Evolve plugins.

The prepared OpenROAD binary includes the V1 loader in
`tools/OpenROAD/src/dpl_evolve/src/EvolvePluginApi.h`.  A plugin can be compiled
as a small shared object and selected with:

```bash
export DPL_EVOLVE_PLUGIN_SO=/abs/path/to/libdpl_evolve_plugin.so
```

Use plugins for fast top-level stage-policy experiments.  If a patch changes
placement data structures, candidate generation, legality checks, or deeper
legalizer internals, use the normal private variant relink path instead.

Current examples:

- `dpl_evolve_plugin_v1/`: minimal V1 plugin that mirrors the built-in default
  stage choice.

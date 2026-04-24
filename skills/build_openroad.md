# Skill: build_openroad

## Purpose
Compile the current `tools/OpenROAD` tree after a candidate patch.

## Preconditions
- Candidate patch is already applied to `tools/OpenROAD/src/dpl_evolve/`
- No unrelated working tree modifications are pending
- Current run packet has been read

## Procedure
1. Move to the ORFS repo root.
   Runtime should be resolved in one explicit way:
   - set `ORFS_ROOT`, or
   - attach an ignored local mount at `$DPL_EVOLVE_AGENT_ROOT/.mounted_orfs`
2. Verify the target plane exists:
   - `tools/OpenROAD/src/dpl_evolve/`
3. Assume external dependencies are already bootstrapped outside the agent loop.
   The agent should not call `./build_openroad.sh --local`.
4. Build or reuse the shared common core first:
   - `"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh"`
   - `"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" 8`
5. For isolated multi-agent / multi-variant runs, prefer the lightweight
   relink path:
   - `"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/agent_a" --dpl-src /abs/path/to/dpl_evolve_variant`
   - source the generated env file:
     `source "${DPL_EVOLVE_STATE_ROOT}/variants/agent_a/variant_env.sh"`
   - then build with:
     `"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh" --threads 8`
   - the relink build emits a private `openroad` and symlinks the common-core
     `sta` into the same variant install directory when `sta` is available
6. If relink is not enough, fall back to the heavier full-variant path:
   - `"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant.sh" --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/agent_a" --dpl-src /abs/path/to/dpl_evolve_variant`
   - `source "${DPL_EVOLVE_STATE_ROOT}/variants/agent_a/variant_env.sh"`
   - `"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_only.sh" 8`
7. For the clean root binary, use the same OpenROAD-only build path without a
   variant env file:
   - `"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_only.sh" 8`
   - the initial OpenROAD-only configure disables OpenROAD tests by default
   - by default it publishes only `openroad` and the optional `sta` binary
     instead of running a full `cmake --install`
   - to keep tests on for debugging, set:
     `OPENROAD_DISABLE_TESTS=0`
8. Treat these files as the primary build evidence:
   - OpenROAD build log: `tools/OpenROAD/build/openroad_build.log`
   - installed binary from the active env:
     - root: `tools/install/OpenROAD/bin/openroad`
     - variant: `${OPENROAD_BINARY}`
     - variant STA helper: `${OPENROAD_INSTALL_ROOT}/bin/sta`
9. If build fails:
   - capture compiler error block
   - record first failing file / symbol / line
   - do **not** immediately broaden patch surface
10. If build succeeds:
   - verify the active `OPENROAD_BINARY` exists, or `tools/install/OpenROAD/bin/openroad` for the clean root build
   - run the lightest available regression or smoke test before full baseline

## Required outputs
- build status
- elapsed build time
- failing source file (if any)
- compiler error excerpt
- binary path / executable timestamp

## Common failure triage
- C++ symbol mismatch after changing method signature
- Tcl wrapper mismatch after changing command arguments
- stale build cache
- missing include or namespace mismatch
- target plane file added but not registered in build system

## Notes for Codex
- Variant builds are supported by:
  - `tools/OpenROAD/src/CMakeLists.txt` via `-D DPL_EVOLVE_SRC_DIR=...`
  - `$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant.sh`
  - `<variant-root>/variant_env.sh`
  - `OPENROAD_BUILD_DIR` / `OPENROAD_INSTALL_ROOT` / `OPENROAD_BINARY`
- Current preferred mode:
  - first build a reusable common core
  - then let each agent rebuild only its own `dpl_evolve`
  - then relink a private `openroad` binary
- Medium-term design note:
  - `$DPL_EVOLVE_AGENT_ROOT/knowledge/plans/common_core_variant_relink.md`

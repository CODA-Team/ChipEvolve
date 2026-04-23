# Skill: build_openroad

## Purpose
Compile the current `tools/OpenROAD` tree after a candidate patch.

## Preconditions
- Candidate patch is already applied to `tools/OpenROAD/src/dpl_evolve/`
- No unrelated working tree modifications are pending
- Current run packet has been read

## Procedure
1. Move to the ORFS repo root that mounts this repo as `evolve_agent/`.
2. Verify the target plane exists:
   - `tools/OpenROAD/src/dpl_evolve/`
3. Assume external dependencies are already bootstrapped outside the agent loop.
   The agent should not call `./build_openroad.sh --local`.
4. For isolated multi-agent / multi-variant runs, configure a dedicated build +
   install root first:
   - `./evolve_agent/scripts/configure_openroad_variant.sh --variant-root ./.codex_state/openroad_variants/agent_a --dpl-src /abs/path/to/dpl_evolve_variant`
   - source the generated env file:
     `source ./.codex_state/openroad_variants/agent_a/variant_env.sh`
   - then build with:
     `./evolve_agent/scripts/build_openroad_only.sh 8`
5. For the clean root binary, use the same OpenROAD-only build path without a
   variant env file:
   - `./evolve_agent/scripts/build_openroad_only.sh 8`
6. Treat these files as the primary build evidence:
   - OpenROAD build log: `tools/OpenROAD/build/openroad_build.log`
   - installed binary from the active env:
     - root: `tools/install/OpenROAD/bin/openroad`
     - variant: `${OPENROAD_BINARY}`
7. If build fails:
   - capture compiler error block
   - record first failing file / symbol / line
   - do **not** immediately broaden patch surface
8. If build succeeds:
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
  - `evolve_agent/scripts/configure_openroad_variant.sh`
  - `<variant-root>/variant_env.sh`
  - `OPENROAD_BUILD_DIR` / `OPENROAD_INSTALL_ROOT` / `OPENROAD_BINARY`
- Current stable mode:
  - first build a variant-specific OpenROAD tree
  - then incrementally rebuild `openroad` in that build dir
- Medium-term design note:
  - `evolve_agent/knowledge/plans/common_core_variant_relink.md`

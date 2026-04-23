# Skill: build_openroad

## Purpose
Compile the current `tools/OpenROAD` tree after a candidate patch.

## Preconditions
- Candidate patch is already applied to `tools/OpenROAD/src/dpl_evolve/`
- No unrelated working tree modifications are pending
- Current run packet has been read

## Procedure
1. Move to ORFS repo root:
   - `/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts`
2. Verify the target plane exists:
   - `tools/OpenROAD/src/dpl_evolve/`
3. For agent loops, prefer the lighter OpenROAD-only path:
   - `./evolve_agent/scripts/build_openroad_only.sh 8`
4. For isolated multi-agent / multi-variant runs, configure a dedicated build +
   install root first:
   - `./evolve_agent/scripts/configure_openroad_variant.sh --variant-root ./.codex_state/openroad_variants/agent_a --dpl-src /abs/path/to/dpl_evolve_variant`
   - then build with:
     `OPENROAD_BUILD_DIR=./.codex_state/openroad_variants/agent_a/build OPENROAD_INSTALL_ROOT=./.codex_state/openroad_variants/agent_a/install/OpenROAD OPENROAD_BINARY=./.codex_state/openroad_variants/agent_a/install/OpenROAD/bin/openroad ./evolve_agent/scripts/build_openroad_only.sh 8`
5. Use the full repo-standard build only when you need to refresh external tools or
   there is no configured OpenROAD build tree yet:
   - `./build_openroad.sh --local`
6. Treat these files as the primary build evidence:
   - repo-level log: `build_openroad.log`
   - OpenROAD build log: `tools/OpenROAD/build/openroad_build.log`
   - installed binary: `tools/install/OpenROAD/bin/openroad`
7. If build fails:
   - capture compiler error block
   - record first failing file / symbol / line
   - do **not** immediately broaden patch surface
8. If build succeeds:
   - verify `tools/install/OpenROAD/bin/openroad` exists
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
- This repo has already been verified to build with both
  `./build_openroad.sh --local` and `./evolve_agent/scripts/build_openroad_only.sh 8`.
- Variant builds are supported by:
  - `tools/OpenROAD/src/CMakeLists.txt` via `-D DPL_EVOLVE_SRC_DIR=...`
  - `evolve_agent/scripts/configure_openroad_variant.sh`
  - `OPENROAD_BUILD_DIR` / `OPENROAD_INSTALL_ROOT` / `OPENROAD_BINARY`
    environment overrides
- A successful incremental build in this workspace also rebuilt and installed
  `dpl_evolve_lib`, `dpl_evolve_py`, `dpl_evolve`, `dpl_evolve_test`, and the
  final `tools/install/OpenROAD/bin/openroad`.

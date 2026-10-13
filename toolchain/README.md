# Toolchain lock

`lock.json` records the observed OpenROAD seed revision, reference-flow revision, and host compiler/CMake/Python versions for the fixed AES artifact. AE-1 checks the shipped inputs; AE-2 records the binary and generated logs. Changing any lock input creates a new artifact claim and requires a new expected manifest.

`environment.yml` is the project-local Conda specification used by `make setup`.
The generated Miniforge installation, Conda environment, Codex CLI, downloads,
and activation script are all ignored below `outputs/toolchain/`. It does not
install OpenROAD or its native build dependencies.

AE-2 and AE-3 deliberately use a separately prepared, version-matched
OpenROAD/ORFS workspace. Activate that workspace in the shell, set
`OPENROAD_EXE` for AE-2, and set a matching `source_root` (or
`GOALEVOLVE_OPENROAD_SEED`) for AE-3. The host workspace owns its compiler,
CMake, native dependencies, shared libraries, and OpenROAD binary.

The release ships all eight contest benchmarks and ASAP7 data under
`third_party/benchmarks/`. The shared source-only OpenROAD p0 lives
at `artifact_evaluation/lineage/openroad_power/p0/source`; verify its manifest
with `python3 artifact_evaluation/verify_openroad_snapshot.py --verify`.

## ChipEvolve common toolchain (opt-in)

`GOALEVOLVE_PLATFORM_PROFILE` selects a runtime JSON outside this source tree.
It fixes the qualified SIF and source commits, private professional source,
new AST root, build flags, installed EF client, resource limits, frozen input
hashes and the original supervision deadline. The profile can explicitly use
`codex.auth_mode=existing_codex` with an existing login directory; native API
mode and the published Codex settings remain available without this profile.

The controller retains native planning, source edits, scoring and selection.
`platform.execution.maybe_delegate` sends deterministic command attempts to EF
with `max_attempts=1`, preserving the native retry count. OpenROAD/builds run
inside the common SIF; the official parser/checker use the independent Python
3.12 environment through EF. Physical evaluations verify a source/binary build
receipt. Large registered evidence is retrieved through the public local
materialization API. This evidence archive is not a DF design snapshot.

Use the root repository's `admin/prepare_common_goalevolve.py` and
`admin/run_common_goalevolve.py` for the recorded local U4 preparation and
phases. Real baseline/evolution/replay and their acceptance are tracked in the
root slice report; integration code alone does not establish those results.

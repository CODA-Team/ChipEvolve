# ChipEvolve integration of TimingECOAgent

Upstream: [ASU-VDA-Lab/TimingECOAgent](https://github.com/ASU-VDA-Lab/TimingECOAgent), commit `80101610d9e39563b76203ab422184ad93d52249`. Original authors, README and PDK notices remain intact. This module is a platform adaptation of that project.

The upstream benchmark `benchmark/AES_55_300/base/6_final.odb` could not be fetched: GitHub LFS returned 404. Its pointer is retained. A real locally generated GCD checkpoint is used for qualification; this does not claim reproduction of that missing upstream benchmark.

The opt-in profile selects existing Codex login, a common OpenROAD container launcher, explicit FF libraries and registered ODB/SDC/SPEF artifacts. Source and run data live in separate directories. Install the published EF client/contracts and Data Interface wheels in this module's independent environment.

```sh
TIMINGECO_PLATFORM_PROFILE=/absolute/run/profile.json .venv/bin/python src/main_orch.py
```

The persistent native controller and all its OpenROAD children belong to one Execution Foundation task. `src/platform_execution.py` first resolves its design snapshot through Data Interface, then submits registered inputs to EF; no unmanaged EDA fallback is provided. `src/platform_codex.py` preserves the original expert prompts and response parser, uses the existing official Codex CLI, and records reported token usage. Subscription monetary cost is not measured.

Native ECO primitives, path context, score weights, backtrace/best-state rules and detailed-route calibration remain upstream behavior. The supported upstream `DRT_EVERY_ITER=1` mode is selected for small GCD. The original one-iteration detailed-route result is separately qualified by a full common-toolchain route and RCX; it is not silently presented as full routing. Exported final artifacts and source hashes are recorded by EF and imported into DF for Query.

Local model connection settings must be explicitly supplied in the profile, because EF strips the host environment. Credentials are never staged or copied into containers. Native mode without the profile remains available.

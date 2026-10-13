# TimingECOAgent in ChipEvolve

- Upstream is ASU-VDA-Lab/TimingECOAgent, pinned in the source manifest. Preserve its provenance, README attribution and all PDK copyright/license headers.
- Preserve original ECO primitives, compressed context, scoring weights, best-state/backtrace policy and full-routing calibration. Platform adaptations change environment/transport boundaries and explicit input configuration.
- A platform session is owned by Execution Foundation. Its persistent OpenROAD process and all children must remain in the supervised EF task tree; do not silently fall back to a host EDA process.
- Codex is an optional model transport using the existing login. Keep prompts and response sanitization; do not copy credentials or reimplement an agent harness.
- Use this project's independent Python environment. Cross-project APIs are installed public wheels/HTTP, never sibling source imports or private service databases.
- Freeze private run copies under var. Never edit an active copy. Do not commit generated design artifacts, credentials, .venv, plots or logs.
- Actual ASAP7 library corner, clock units and source/binary/input identity must match the experiment. Missing upstream LFS benchmark files are known evidence, not successful downloads.
- Unit/static, source-diff and boundary checks precede real GCD evaluation. A runnable integration does not imply improved PPA or original benchmark reproduction.

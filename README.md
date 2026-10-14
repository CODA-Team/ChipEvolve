# A2-ORFO

A2-ORFO optimizes physical-design configurations through staged OpenROAD flows,
agent-guided proposals, and doomed-run prediction. This repository packages the
DRP-Agent implementation with ASAP7 and Nangate45 AES, IBEX, and JPEG benchmarks.

The comparison objective is **minimum terminal |TNS at fixed CP0|, subject to power
not exceeding the baseline**. The supplied configuration retains `gpt-5.6-sol`.

## Repository instructions

```text
A2-ORFO/
├── run.sh                # Public campaign entry point
├── config/               # Environment setup and API template
├── flow/                 # Self-contained optimizer + ORFS flow workspace
│   ├── drp_config.json    # Algorithm, model and objective settings
│   ├── maindriver.sh      # Low-level staged driver
│   ├── *.py              # Optimizer modules
│   ├── designs/          # Six benchmark configs and licensed RTL
│   ├── predict_model/    # QoR-comparator code and checkpoint
│   ├── scripts/, util/   # ORFS Tcl scripts and helper utilities
│   ├── platforms/       # Included platform libraries
│   └── test/            # Upstream flow tests
├── requirements/         # Runtime, development and reference dependencies
├── RUNNING.md            # Installation and execution guide
└── licenses/             # Preserved third-party licenses
```

Keeping the runtime in one `flow/` workspace preserves ORFS's relative-path
contracts and the optimizer's existing imports. Platform data is included in this
checkout; generated experiment outputs are excluded from Git.

## Quick start

Use Linux with Python 3.12 and a working OpenROAD/Yosys ORFS toolchain. IBEX needs
the Yosys slang frontend. See the [running guide](RUNNING.md) for prerequisites.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/requirements.txt
# Platform libraries are already included in flow/platforms/.
cp config/api.sh.example config/api.sh
# Edit config/api.sh with your API endpoint/key; put tool binaries on PATH.
./run.sh -p asap7 -d aes -o TNS_EVAL \
  -i 25 -r 50 -s gwtw -A -P -F --seed 42 --cpus 250 -t 120m
```

`-F` starts a fresh campaign and archives previous campaign state. Results and
logs are written inside `flow/`. 

For an existing ChatGPT/Codex CLI login, use `DRP_LLM_TRANSPORT=codex ./run.sh ...`
without an API key. This optional transport represents configuration tool decisions
through structured CLI output; see [account setup and limitations](RUNNING.md#using-an-existing-chatgptcodex-account).
Use `-A -N` for numerical Agentic runs without external LLM requests.

## Documentation

- [Installation and execution](RUNNING.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)


## License

This repository is released under the MIT License. See [LICENSE](./flow/predict_model/transformer_code/LICENSE).

Third-party tools and libraries, including OpenROAD/OpenROAD-flow-scripts, are not redistributed by this repository and remain subject to their own licenses.

## Citation

If you use this code in academic work, please cite the corresponding paper. Full citation information can be added here after publication.

## Shared final objective (platform mode)

Install the platform's current `eda-toolkits` wheel in this project's Python
environment. Set `EDA_PLATFORM_OBJECTIVE` to the absolute path of the same frozen
`chip-evolve.objective.v1` JSON used by the other professional projects and final
measurements. Enable this project's existing platform backend as usual.

The actual model prompt receives the team's final clock, library hashes, power
and cell/core/die area limits. EF tasks stage the goal and record `objective_id`
and `final_condition_id`; source execution receipts bind its file hash. If a
profile also specifies `objective_path`, it must identify the same frozen goal.
Native search, scoring, promotion and exploratory tradeoffs remain unchanged;
Codex makes final adoption decisions using comparable final measurements.
Without the explicit objective setting, the original model prompt is retained.

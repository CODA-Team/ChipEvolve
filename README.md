# A2-ORFO

A2-ORFO optimizes physical-design configurations through staged OpenROAD flows,
agent-guided proposals, and doomed-run prediction. This repository packages the
DRP-Agent implementation with ASAP7 and Nangate45 AES, IBEX, and JPEG benchmarks.

The comparison objective is **minimum terminal |TNS at fixed CP0|, subject to power
not exceeding the baseline**. The supplied configuration retains `gpt-5.6-sol`.

## Repository layout

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
│   ├── tests/, test/     # Optimizer tests and upstream flow tests
│   └── analysis_tools/   # Experiment analysis utilities
├── requirements/         # Runtime, development and reference dependencies
├── tools/                # Setup, testing and release checks
├── docs/                 # Run guide, architecture and validation records
└── licenses/             # Preserved third-party licenses
```

Keeping the runtime in one `flow/` workspace preserves ORFS's relative-path
contracts and the optimizer's existing imports. Platform data and experiment
outputs are runtime assets excluded from Git.

## Quick start

Use Linux with Python 3.12 and a working OpenROAD/Yosys ORFS toolchain. IBEX needs
the Yosys slang frontend. See the [running guide](docs/RUNNING.md) for prerequisites.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/requirements.txt
python tools/setup_platforms.py --flow-root /path/to/OpenROAD-flow-scripts/flow
cp config/api.sh.example config/api.sh
# Edit config/api.sh with your API endpoint/key; put tool binaries on PATH.
./run.sh -p asap7 -d aes -o TNS_EVAL \
  -i 25 -r 50 -s gwtw -A -P -F --seed 42 --cpus 250 -t 120m
```

`-F` starts a fresh campaign and archives previous campaign state. Results and
logs are written inside `flow/`. 

## Documentation

- [Installation, execution and publishing](RUNNING.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)


## License

This repository is released under the MIT License. See [LICENSE](A2-ORFO/flow/predict_model/transformer_code/LICENSE).

Third-party tools and libraries, including OpenROAD/OpenROAD-flow-scripts, are not redistributed by this repository and remain subject to their own licenses.

## Citation

If you use this code in academic work, please cite the corresponding paper. Full citation information can be added here after publication.


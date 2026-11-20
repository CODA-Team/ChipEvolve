# ChipEvolve

ChipEvolve connects Codex to OpenROAD. Give Codex a design goal, such as preserving timing while reducing power. Codex reads the measured design through the Analysis Agent, hands the design and a budget to a specialist, and uses the returned evidence to decide what to try next.

```text
ChipEvolve/
├── chip-evolve.py           # Codex calls this to run, inspect, and compare experiments
├── agent/
│   ├── query-agent/         # Analysis Agent: find and explain design facts
│   ├── flow-agent/          # Tune ORFS parameters and constraints
│   ├── dplevolve/           # Evolve detailed-placement algorithms
│   ├── goalevolve/          # Evolve optimization algorithms for a QoR goal
│   └── timing-eco-agent/    # Repair timing on a routed design
├── data-foundation/        # Parse and connect design facts
├── data-interface/         # Python SDK for those facts
├── execution-foundation/   # Schedule jobs, track resources, and register artifacts
└── toolkits/               # Run ORFS and OpenROAD and export their results
```

The root package `chip_evolve/` implements the commands behind `chip-evolve.py`. The nine modules are Git submodules, each pinned to a specific revision. See [Architecture](ARCHITECTURE.md) for the path a design takes through the system and [Task status](TASKS.md) for the scope of current validation.

## Run the small GCD example

Use a checkout of the engineering candidate with all nine pinned submodules initialized. You need Linux, Git, Python 3.12 with `venv`, Apptainer, and an ORFS SIF with the Nangate45 GCD example. The qualified image is based on ORFS `5105b0a77` and OpenROAD `27288f5c90`. Pass its absolute path in `ORFS_SIF`. The hardware reservation for the GCD flow is eight CPU cores and 4 GiB of memory.

The pinned ORFS manifest is available from Docker Hub. Build a local SIF under `var/`.

```bash
mkdir -p var/toolchain
apptainer pull var/toolchain/orfs.sif docker://openroad/orfs@sha256:212127afc6538596e9c819ecea4830ec7edb76e2fca51f8dcd741c772558d4e0
export ORFS_SIF="$PWD/var/toolchain/orfs.sif"
```

Run these commands from the repository root in a fresh checkout.

```bash
git submodule update --init --recursive
python3 admin/bootstrap.py --output var/bootstrap

python3 admin/release/stack.py init --workspace . --instance gcd-demo \
  --image "$ORFS_SIF" --config var/gcd-stack.json
python3 admin/release/stack.py prepare-gcd --config var/gcd-stack.json
python3 admin/release/stack.py start --config var/gcd-stack.json

local_config=var/instances/gcd-demo/local.json
python3 chip-evolve.py --config "$local_config" run \
  --design gcd --capability orfs --key baseline --seconds 300
python3 chip-evolve.py --config "$local_config" show \
  --result var/instances/gcd-demo/experiments/gcd/baseline/result.json
```

`prepare-gcd` extracts the Nangate45 Liberty and GCD constraints from the image and sets a 500 ps clock. The example stores its experiment and service state in `var/instances/gcd-demo/`. For a machine with a third-party wheel cache, pass `--dependencies /path/to/wheels` to `bootstrap.py`. The image's pinned OCI source is recorded in the [toolchain audit](admin/COMMON_TOOLCHAIN_AUDIT_20261012.md).

To observe an experiment, use `status --design gcd` or `watch --design gcd --run-id RUN_ID`. If delivery was interrupted, use `resume --design gcd --key baseline` to recover that experiment. `show` includes the analysis snapshot IDs. With a Codex CLI login, run `diagnose --result RESULT_JSON` to create a cited professional context. A specialist run uses `run --capability flow|dpl|goal|eco --source RESULT_JSON --context CONTEXT_JSON` plus the design, new key, and budget. Specialist runtimes have their own documented setup and require the corresponding `professional` deployment binding.

Stop the instance after using it.

```bash
python3 admin/release/stack.py stop --config var/gcd-stack.json
```

## Try the Timing ECO handoff

Install the ECO environment before preparing the example and pass `--eco-python` to `prepare-gcd`. This extracts the Nangate45 routing inputs from the same image and binds the TimingECOAgent submodule.

```bash
python3 -m venv agent/timing-eco-agent/.venv
eco_python=agent/timing-eco-agent/.venv/bin/python
"$eco_python" -m pip install -r agent/timing-eco-agent/requirements.txt
"$eco_python" -m pip install --pre --no-index --find-links var/bootstrap/packages \
  openroad-platform-client eda-ai-client eda-toolkits
python3 admin/release/stack.py prepare-gcd --config var/gcd-stack.json \
  --eco-python "$eco_python"
```

With the stack running and a baseline result, use the Codex CLI login to create the diagnosis. Take its `context` path from the printed JSON and pass it to the specialist.

```bash
result=var/instances/gcd-demo/experiments/gcd/baseline/result.json
python3 chip-evolve.py --config "$local_config" diagnose --result "$result"
python3 chip-evolve.py --config "$local_config" run --design gcd \
  --capability eco --source "$result" --context "$CONTEXT_JSON" \
  --key eco-one --rounds 1 --seconds 240
python3 chip-evolve.py --config "$local_config" diagnose \
  --result var/instances/gcd-demo/experiments/gcd/eco-one/result.json \
  --against "$result"
```

The GitHub release will need the candidate's pinned branches to be published and independently checked from a public clone. The engineering candidate and existing public `main` are different revisions. Historical experiment records remain in Git and under `admin/`, and the previous implementation is in [`discarded/`](discarded/).

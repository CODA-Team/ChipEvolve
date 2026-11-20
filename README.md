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

The root package `chip_evolve/` implements the commands behind `chip-evolve.py`. The nine modules are Git submodules, each pinned to a specific revision. Use the [Agent dispatch table](agent/README.md) to choose a specialist based on the evidence, the starting point, and the permitted changes. See [Architecture](ARCHITECTURE.md) and [Task status](TASKS.md) for workflow and validation scope.

## Run the small GCD example

Use a checkout of the engineering candidate with all nine pinned submodules initialized. You need Linux, Git, Python 3.12 with `venv`, Apptainer, and an ORFS SIF with the Nangate45 GCD example. The qualified image is based on ORFS `5105b0a77` and OpenROAD `27288f5c90`. Pass its absolute path in `ORFS_SIF`. The GCD flow reserves up to eight available CPU cores and 4 GiB of memory. To set smaller stack capacity, pass `--cpu-cores` and `--memory-gib` to `init`.

```bash
git clone --branch engineering/cleanup-b6cfd1d https://github.com/CODA-Team/ChipEvolve.git
cd ChipEvolve
```

The pinned ORFS manifest is available from Docker Hub. Build a local SIF under `var/`.

```bash
mkdir -p var/toolchain
apptainer pull var/toolchain/orfs.sif docker://openroad/orfs@sha256:212127afc6538596e9c819ecea4830ec7edb76e2fca51f8dcd741c772558d4e0
export ORFS_SIF="$PWD/var/toolchain/orfs.sif"
```

That manifest is for x86_64. On Linux aarch64, use Docker with Buildx and
Apptainer to build the same ORFS and OpenROAD source revisions natively.
The ARM64 script uses the checked-out Slang submodule and the CMake CLI build.

```bash
mkdir -p var/toolchain
bash admin/release/build_arm_orfs.sh var/toolchain/orfs-source var/toolchain/orfs-arm64.sif
export ORFS_SIF="$PWD/var/toolchain/orfs-arm64.sif"
```

Run these commands from the repository root in a fresh checkout.

```bash
bash admin/checkout_modules.sh
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

`bootstrap.py` builds the platform wheels from committed sources and installs the nine module environments plus the root test environment. It uses CPU-only PyTorch for Flow. For an offline install, pass `--dependencies /path/to/wheels` with the wheels for the host architecture and the [dependency constraints](admin/requirements-constraints.txt). `prepare-gcd` extracts the Nangate45 Liberty and GCD constraints from the image and sets a 500 ps clock. The example stores its experiment and service state in `var/instances/gcd-demo/`. The image's pinned OCI source is recorded in the [toolchain audit](admin/COMMON_TOOLCHAIN_AUDIT_20261012.md).

The checkout script keeps Git LFS pointers and fetches the GoalEvolve runtime and checkers. The GCD example generates its own checkpoints. For the GoalEvolve paper archive, run `git -C agent/goalevolve sparse-checkout disable` to fetch the full working tree, which takes about 16 GiB. The TimingECOAgent upstream benchmark archive has separate LFS availability.

To observe an experiment, use `status --design gcd` or `watch --design gcd --run-id RUN_ID`. If delivery was interrupted, use `resume --design gcd --key baseline` to recover that experiment. `show` includes the analysis snapshot IDs. With a Codex CLI login, run `diagnose --result RESULT_JSON` to create a cited professional context. A specialist run uses `run --capability flow|dpl|goal|eco --source RESULT_JSON --context CONTEXT_JSON` plus the design, new key, and budget. Specialist runtimes have their own documented setup and require the corresponding `professional` deployment binding.

Stop the instance after using it.

```bash
python3 admin/release/stack.py stop --config var/gcd-stack.json
```

## Try the Timing ECO handoff

When preparing a new instance, pass the TimingECOAgent interpreter installed by `bootstrap.py` to `prepare-gcd`. This extracts the Nangate45 routing inputs from the same image and binds the TimingECOAgent submodule.

```bash
python3 admin/release/stack.py prepare-gcd --config var/gcd-stack.json \
  --eco-python "$PWD/agent/timing-eco-agent/.venv/bin/python"
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

## Try native Flow search

When initializing a fresh instance, pass `--flow` to `prepare-gcd`. It takes
the binaries and their hashes from the same ORFS image and prepares a GCD
recipe with a fixed clock and independent floorplan and routing controls.
The three-candidate example requires two valid original identities at the
selection checkpoints and keeps any failed runs in the evidence. Use that
instance's ORFS result as the source. After `diagnose` returns its
context, pass the source and context to Flow.

```bash
python3 chip-evolve.py --config "$local_config" run --design gcd \
  --capability flow --flow-recipe source --source "$result" \
  --context "$CONTEXT_JSON" --key flow-two --rounds 2 --candidates 3 --seconds 1500
```

## Prepare the C++ specialists

Start a GCD instance with `--memory-gib 64` on `stack.py init` for a cold
OpenROAD build. DPLEvolve uses `rsync` for its native seed preparation. With
the stack running, prepare the two specialist bindings from their pinned
public source and existing research patches.

```bash
python3 admin/release/prepare_dpl.py --config var/gcd-stack.json
python3 admin/release/prepare_goal.py --config var/gcd-stack.json
```

The DPL preparation submits the common core build to Execution Foundation.
GoalEvolve submits its baseline build when dispatched. Run the normal GCD
baseline and diagnosis, then hand off their result and context with
`run --capability dpl` or `run --capability goal`. See the
[Agent dispatch table](agent/README.md) for the placement and algorithm
boundaries and the required evidence.

## Check the workspace

With the module development environments set up, run `python3 dev.py all check`
to run the nine module checks and the root regression suite. Each module uses
its own `.venv`. The root suite uses `admin/.venv` and its tests are named
`admin/test_*.py`. To check a separate installation of one module, run
`python3 dev.py --python /path/to/venv/bin/python MODULE check`.
GoalEvolve's platform check runs `tests/unit`. With the paper archive checked
out, run `python3 dev.py goalevolve check tests/artifact` to check its layout
and manifests as well.

The release candidate is published on `engineering/cleanup-b6cfd1d`. See [engineering status](TASKS.md) for verified platforms and specialist runs. Historical experiment records remain in Git and under `admin/`, and the previous implementation is in [`discarded/`](discarded/).

## License

The ChipEvolve workspace is available under the MIT License. Each submodule's license and source notices govern its own components. [License](LICENSE)

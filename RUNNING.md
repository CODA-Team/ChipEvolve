# Installation and execution

## Environment

Run from the repository root on Linux. Install Python 3.12, GNU Make, Bash, GNU
coreutils (`timeout`) and a matching ORFS OpenROAD/Yosys toolchain. IBEX requires
the Yosys slang frontend; finish/report stages may also require KLayout and ORFS
auxiliary tools. Use the same tool builds and platform data for comparisons.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/requirements.txt
cp config/api.sh.example config/api.sh
```

Edit `config/api.sh` with your endpoint/key. The wrapper sources it automatically.
For binaries not on PATH, create ignored `config/env.local.sh`:

```bash
export OPENROAD_EXE=/path/to/openroad
export YOSYS_EXE=/path/to/yosys
export STA_EXE=/path/to/sta
```

`run.sh` activates the root `.venv` when present, sources local configuration,
checks the tool paths, changes into `flow/`, and invokes `maindriver.sh`.
Direct dependencies are in `requirements/requirements.txt`; the reference file
records the input environment's versions and is not a clean-room lock file.

## Campaign

```bash
chmod +x run.sh
./run.sh -p nangate45 -d aes -o TNS_EVAL \
  -i 25 -r 50 -s gwtw -A -P -F --seed 42 --cpus 250 -t 120m
```

- `-i 25`: 25 iterations; `-r 50`: 50 slots per iteration.
- `--cpus 250`: total thread budget, giving 5 threads per flow at 50 slots.
- `-t 120m`: per-stage timeout, not a whole-campaign deadline.
- `-A -P`: agentic optimization and QoR-comparator ranking.
- `-F`: fresh campaign with previous state archived. The default `-k` remains 2.
- Model settings and power budget are in `flow/drp_config.json`.

Keep the same candidate budget and evaluation references when comparing methods.
The wrapper runs in the foreground. To launch in the background:

```bash
mkdir -p flow/logs
LOG="flow/logs/campaign_$(date +%Y%m%d_%H%M%S).log"
nohup ./run.sh -p nangate45 -d aes -o TNS_EVAL \
  -i 25 -r 50 -s gwtw -A -P -F --seed 42 --cpus 250 -t 120m > "$LOG" 2>&1 &
echo "PID=$! LOG=$LOG"
tail -F "$LOG"
```

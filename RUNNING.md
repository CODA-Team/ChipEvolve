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
This is optional for numerical runs (`-N`) and for the Codex account transport below.
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

## Using an existing ChatGPT/Codex account

The optional `codex` transport uses the official Codex CLI's existing login. It
requires a CLI supporting `exec --json --output-schema --ignore-user-config`;
version 0.159.3 was tested on this server. Run `codex login status` to check login,
or `codex login` to sign in. No API key is needed for this transport.

```bash
DRP_LLM_TRANSPORT=codex ./run.sh -p nangate45 -d aes -o TNS_EVAL \
  -i 2 -r 3 -k 1 -s elitist -A -P -F \
  --seed 42 --cpus 12 --max-concurrent-runs 3 -t 10m
```

Omit `-N` to enable actual LLM requests. `DRP_LLM_TRANSPORT=codex` selects the
transport for both `llm` and `supervisor`; alternatively set `"transport": "codex"`
in each configuration block. The default remains the OpenAI-compatible API.
Keep a model available to your account in both blocks; `gpt-5.6-sol` was tested.
The CLI uses its own credential storage/refresh and the server's proxy environment.
This adapter never reads or copies OAuth tokens into an API key.

Each call starts an ephemeral, isolated, read-only CLI session. Configuration
tools are represented by structured output and interpreted by the existing Python
optimizer. They are not native Chat Completions tool calls. Model decisions still
choose the inspection, surrogate, and selection configurations, and the project
runs the corresponding numerical functions. The CLI is instructed to use no tools;
unexpected tool activity is rejected.

`codex_reasoning_effort` defaults to `low` in each config block; `timeout` bounds
each call. API `temperature` and `max_tokens` are not applied by the CLI transport.
Its input includes CLI instructions, so account usage is larger than the project
prompt alone. The campaign ledger records the CLI's actual input/output/cache/
reasoning counts; an unreported response model id stays empty. For optional local
response audits, set `DRP_CODEX_AUDIT_DIR` to an ignored directory under `validation/`.
The optimizer's existing fallback behavior still applies when requests fail: check
the usage ledger and warnings to distinguish real LLM decisions from fallback.

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
- Multi-iteration `-A` campaigns require at least 3 runs; Agent2 reserves two
  front slots and at least one exploration slot. Use `-A -N` to exercise numerical
  optimization without external LLM requests.

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

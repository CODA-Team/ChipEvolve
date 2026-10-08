# eda-ai-client

Read-only Python client for the **EDA-AI Data Interface**. It gives a model, or a
partner's agent runtime, structured OpenROAD / ORFS facts without knowing
anything about ODB, DEF, SPEF, report formats or where the files live.

- standard library only, no dependencies
- imports nothing from this repository's applications
- tool surface is `CONTRACT.md` v0.1; every response keeps the service's
  `status` / `missing` / `evidence` semantics instead of flattening them

## Install

```bash
python -m venv /tmp/clean
/tmp/clean/bin/pip install ./clients/eda_ai_client        # or: pip install eda-ai-client
```

## Use

```python
from eda_ai_client import EdaAiClient

with EdaAiClient(data_url="http://127.0.0.1:8860",
                 kernel_url="http://127.0.0.1:8700") as client:
    for design in client.list_designs():
        print(design["design_id"], design["revisions"])

    stage = client.get_stage_summary("ibex-eda_ai_sprint_b1-route")
    print(stage["record_counts"])          # {'entities': 189054, ...}

    metrics = client.get_metrics(run_id="run-f0adf…", stage="finish")
    for row in metrics["metrics"]:
        print(row["name"], row["value"], row["unit"], row["status"])
        # WNS -0.0158581 ns available

    paths = client.get_timing_paths("ibex-eda_ai_sprint_b1-route", check="setup")
    detail = client.get_timing_path(paths["snapshot_id"], paths["timing_paths"][0]["path_id"],
                                    include="points")

    instance = client.get_instance("ibex-eda_ai_sprint_b1-route", "_19891_")
    evidence = client.get_evidence("ibex-eda_ai_sprint_b1-route", limit=5)
```

`data_url` serves facts. `kernel_url` is only needed for `list_runs`,
`list_artifacts` and `artifact_bytes`; a caller that only wants design facts can
leave it unset and the three will raise a clear error.

## The twelve tools

| tool | needs kernel | notes |
|---|---|---|
| `list_designs()` | no | grouped client-side from snapshots |
| `list_runs(design_id, stage, status)` | yes | kernel indexes runs, not stages |
| `get_run_summary(run_id)` | no | every stage snapshot of the run |
| `get_stage_summary(snapshot_id)` | no | counts + per-domain coverage |
| `list_artifacts(run_id, kind)` | yes | raw artifacts of the run |
| `get_metrics(run_id, snapshot_id, stage, name, include_raw)` | no | canonical names only; `include_raw=True` adds the rest by raw key |
| `get_timing_paths(snapshot_id, check)` | no | `check` is `setup` or `hold` |
| `get_timing_path(snapshot_id, path_id, include)` | no | `summary` / `points` / `context` |
| `get_instance(snapshot_id, name)` | no | exact name; 0 hits → `not_found`, >1 → `partial` |
| `get_net_context(snapshot_id, net)` | no | accepts a net object ID or an exact name |
| `get_physical_context(snapshot_id, object_id)` | no | bbox / geometry / routing |
| `get_evidence(snapshot_id, record_type, record_id, artifact_id)` | no | source locations behind the facts |
| `artifact_bytes(run_id, artifact_id)` | yes | original bytes; verify the `sha256` from evidence |

## Status semantics

A missing fact is never an empty value. The service answers with a `status` from
`available | partial | unavailable | truncated | not_found | incomparable`, plus
`reason` and `missing`. Callers are expected to refuse to answer rather than
substitute neighbouring data - that is the property the benchmark measures.

## Demo

```bash
python clients/eda_ai_client/examples/smoke_all_tools.py            # from a clean venv
bash evidence/C/clean_env_demo.sh                                   # builds the clean venv for you
```

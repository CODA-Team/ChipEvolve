# Agentic EDA Query Agent

This repository is the Phase IV foundation for an evidence-first Query Agent
for ASIC physical design and OpenROAD. It intentionally does not parse DEF,
SPEF, ODB or timing graphs, execute shell commands, or run an agent framework.

The core pipeline is ordinary Python:

```text
QueryRequest -> intent -> QueryPlan -> providers -> Evidence
             -> deterministic sufficiency -> QueryResponse
```

The filesystem adapter is read-only and sandboxed to one workspace. Design-data
and execution-backed analysis are typed ports with explicit fixture and
unavailable boundaries.
See [`docs/execution-foundation-integration.md`](docs/execution-foundation-integration.md)
for the recommended future integration.

The current capability status and overnight review package are in
[`docs/capability-matrix.md`](docs/capability-matrix.md) and
[`docs/tomorrow-report.md`](docs/tomorrow-report.md). A five-minute local demo
is available at [`demo/demo_phase1.sh`](demo/demo_phase1.sh); set
`EDA_CORPUS_ROOT` to a real EDA-Corpus checkout to exercise the knowledge
provider.

## Development

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
pyright
lint-imports
pytest
```

The project has no dependency on the execution-foundation Python packages.

## 独立开发工作区（2026-10-08）

这是主 Query Agent 实现，保留原独立仓库的未提交工作。原平台 apps/query_agent
是不同的历史服务实现；没有并入本项目。
使用上级 `python3 dev.py query-agent check` 或 `python3 dev.py query-agent shell`。
执行平台走 HTTP 适配器；当前设计数据 provider 仍是 unavailable，Data Interface
SDK 接入需要后续实现。不要把目录独立误当作该能力已经接通。

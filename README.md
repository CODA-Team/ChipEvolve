# Agentic EDA Query Agent

This repository is the Phase III-B foundation for an evidence-first Query Agent
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

# Agent Handoff

Current handoff (2026-10-08) supersedes the historical slice below. Develop in this
independent project. DataFoundationProvider and DataExperimentProvider consume
installed SDK wheels/public HTTP; never open either service database. Strict
checks pass (87 tests and 3 import contracts). Real STA/registered evidence,
comparison, cancellation and restart acceptance is in the workspace report.
Remaining work is typed physical/relations, explicit supplementary-analysis
requests and broader real design benchmarks. Preserve missing-data boundaries.
The original uncommitted work is backed up in ../admin/refinement-baseline.

## Historical slice

Last verified state: real ASAP7 GCD run catalog and report query passed; fixture gates green.

Current priority: complete the registered-run foundation before design-data work.

What was just completed: design-scoped run listing, exact artifact lookup,
registered source excerpts, verified binary retrieval, official ORFS key-metric
reporting, and explicit evidence levels. The real run
`run-fd0b7130b99543db9d1b6292dae4e442` registered 112 artifacts.

Exact next action: define a linked supplementary report run using frozen
registered artifacts from a selected source run. Execute only through the
execution foundation; preserve source run, artifact hashes, tool version and
new report provenance. Do not mutate the source run or claim fixture diagnosis
is production-ready.

Files currently relevant:

- `src/query_agent/domain/`
- `src/query_agent/ports/run_evidence.py`
- `src/query_agent/ports/analysis.py`
- `src/query_agent/ports/diagnosis.py`
- `src/query_agent/adapters/run_evidence/`
- `src/query_agent/adapters/analysis/`
- `src/query_agent/adapters/diagnosis/`
- `src/query_agent/application/`
- `tests/fixtures/fake_execution.py`
- `tests/unit/`, `tests/integration/`, and `benchmarks/phase4/`

Commands to run first:

```text
ruff check . && ruff format --check . && pyright && lint-imports && pytest
```

Known failing tests: none in the Query Agent suite after this slice.

External blockers: none. The execution foundation is reachable on `eda-proxy`;
the Query Agent must use its public service API rather than its private state.

Do not redo: Phase-I provider/benchmark design or Phase-II selection semantics;
preserve both while adding later capability ports.

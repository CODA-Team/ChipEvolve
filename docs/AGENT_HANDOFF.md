# Agent Handoff

Last verified state: Phase-II complete and all gates green on 2026-09-22.

Current phase/slice: Phase II / 2.5 complete.

What was just completed: structured experiment context contracts, execution
foundation adapter, deterministic selection/freshness/conflict/comparison
policies, QueryTrace integration, and the 9-case Phase-II benchmark.

Exact next action: start Phase III-A only after preserving the Phase-II gate;
add a typed design-data provider behind a new port when an authoritative data
foundation is available.

Files currently relevant:

- `src/query_agent/domain/`
- `src/query_agent/ports/run_evidence.py`
- `src/query_agent/adapters/run_evidence/`
- `src/query_agent/application/`
- `tests/fixtures/fake_execution.py`
- `tests/unit/` and `tests/integration/`

Commands to run first:

```text
ruff check . && ruff format --check . && pyright && lint-imports && pytest
```

Known failing tests: none.

External blockers: none. The execution-foundation source is available locally,
but only its public HTTP client surface may be used.

Do not redo: Phase-I provider/benchmark design or Phase-II selection semantics;
preserve both while adding later capability ports.

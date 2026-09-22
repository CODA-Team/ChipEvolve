# Agent Handoff

Last verified state: Phase-III-A typed design-data slice complete; gates green.

Current phase/slice: Phase III-A / 3.1 complete.

What was just completed: structured experiment context contracts, execution
foundation adapter, deterministic selection/freshness/conflict/comparison
policies, QueryTrace integration, typed design-data operations, and the 8-case
Phase-III-A benchmark.

Exact next action: begin Phase III-B with a narrow read-only analysis contract;
do not add timing graph traversal or tool execution until an authoritative
analysis provider boundary is specified.

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

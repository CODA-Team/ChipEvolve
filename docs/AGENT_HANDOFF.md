# Agent Handoff

Last verified state: Phase-III-B typed timing-analysis slice complete; gates green.

Current phase/slice: Phase III-B / 3.2 complete.

What was just completed: structured experiment context contracts, execution
foundation adapter, deterministic selection/freshness/conflict/comparison
policies, QueryTrace integration, typed design-data operations, bounded timing
analysis evidence, and the Phase-III-A/III-B benchmarks.

Exact next action: preserve the analysis contract while preparing Phase IV's
separate evidence-grounded diagnosis boundary; do not add timing graph
traversal, tool execution, or action capabilities.

Files currently relevant:

- `src/query_agent/domain/`
- `src/query_agent/ports/run_evidence.py`
- `src/query_agent/ports/analysis.py`
- `src/query_agent/adapters/run_evidence/`
- `src/query_agent/adapters/analysis/`
- `src/query_agent/application/`
- `tests/fixtures/fake_execution.py`
- `tests/unit/`, `tests/integration/`, and `benchmarks/phase3b/`

Commands to run first:

```text
ruff check . && ruff format --check . && pyright && lint-imports && pytest
```

Known failing tests: none.

External blockers: none. The execution-foundation source is available locally,
but only its public HTTP client surface may be used.

Do not redo: Phase-I provider/benchmark design or Phase-II selection semantics;
preserve both while adding later capability ports.

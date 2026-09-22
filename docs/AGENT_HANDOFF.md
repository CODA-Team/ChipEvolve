# Agent Handoff

Last verified state: Phase-IV evidence-linked diagnosis slice complete; gates green.

Current phase/slice: Phase IV / 4.1 complete.

What was just completed: structured experiment context contracts, execution
foundation adapter, deterministic selection/freshness/conflict/comparison
policies, QueryTrace integration, typed design-data operations, bounded timing
analysis evidence, evidence-linked diagnosis, and the Phase-III-A/III-B/IV
benchmarks.

Exact next action: preserve the diagnosis contract while preparing a separate
Phase V action boundary; do not add autonomous repair, tool execution, or
causal confidence heuristics.

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

Known failing tests: none.

External blockers: none. The execution-foundation source is available locally,
but only its public HTTP client surface may be used.

Do not redo: Phase-I provider/benchmark design or Phase-II selection semantics;
preserve both while adding later capability ports.

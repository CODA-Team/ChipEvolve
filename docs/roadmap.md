# Query Agent roadmap

The project grows by adding evidence contracts and external providers, not by
moving algorithms into the kernel. Each milestone keeps retrieval and
answerability deterministic; language models remain typed edges around that
pipeline.

## Status

| Milestone | Status | Evidence |
| --- | --- | --- |
| P0: evidence-first foundation | complete | typed domain, ports, read-only local provider |
| P1: managed run vertical slice | complete | execution-foundation public read API adapter |
| P1: correctness and benchmark | complete | 30 deterministic cases, scope/conflict/stale tests |
| P1: typed natural-language edge | complete | fake model, schema validation, versioned prompts |
| P1: CLI and trace | complete | `query-agent ask`, benchmark command, `QueryTrace` |
| P2: EDA-Corpus knowledge | complete when checkout is supplied | lexical QA and prompt-script CSV provider |
| Phase II: experiment context reasoning | complete | typed run/stage/context provider, deterministic selection, freshness/conflict/comparison policies |
| Phase III-A: design-object understanding | complete (fixture-backed contract) | typed instance/net/pin/location/connection/fanout/region port, application integration, 8-case benchmark |
| Phase III-B: analysis understanding | complete (fixture-backed contract) | scoped WNS/TNS and timing-path port, application integration, 5-case benchmark |
| Phase IV: evidence-grounded diagnosis | complete (fixture-backed contract) | evidence-linked findings with typed support, scope, and refusal semantics |
| Phase V: action / optimization | planned | explicit reversible execution contract |

## Near-term sequence

1. Preserve all four completed context/design/analysis/diagnosis benchmarks.
2. Add diagnosis comparison only when conflict and support semantics are
   explicit.
3. Define action as a separate reversible contract; do not widen findings into
   autonomous execution.

## Explicit non-goals

Phase I does not parse DEF/ODB/SPEF, infer timing paths, execute EDA tools,
create tasks, or use an autonomous multi-agent graph. Those capabilities need
new contracts and authoritative evidence first.

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
| Phase II: experiment context reasoning | in progress | typed run/stage/context provider, deterministic selection, freshness/conflict/comparison policies |
| Phase III-A: design-object understanding | planned | future data foundation contract |
| Phase III-B: analysis understanding | planned | requires typed analysis provider |
| Phase IV: evidence-grounded diagnosis | planned | requires cell/net/path/region evidence |
| Phase V: action / optimization | planned | explicit reversible execution contract |

## Near-term sequence

1. Complete the Phase-II context benchmark and preserve its selection/rejection
   reason codes in `QueryTrace`.
2. Add a public design-data contract only when the data foundation can expose
   scoped, provenance-bearing objects.
3. Add bounded analysis requests through the execution foundation rather than
   introducing shell execution or a second orchestration framework.

## Explicit non-goals

Phase I does not parse DEF/ODB/SPEF, infer timing paths, execute EDA tools,
create tasks, or use an autonomous multi-agent graph. Those capabilities need
new contracts and authoritative evidence first.

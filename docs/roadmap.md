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
| Run artifact foundation | verified on a real OpenROAD run | design/run listing, 112 registered artifacts, exact source excerpts, verified original-file retrieval, cited key metrics |
| Supplementary official reports | in progress | stage frozen source artifacts into a linked analysis run; invoke admitted official reporting commands |
| Phase V: action / optimization | planned | explicit reversible execution contract |

## Near-term sequence

1. Preserve the real run catalog and evidence tests alongside the fixture benchmarks.
2. Implement linked, read-only OpenROAD report runs from registered source artifacts.
3. Record shared dependency fingerprints, then address history and pagination.
4. Keep diagnosis and repair behind the future design-data boundary.

## Explicit non-goals

Phase I does not parse DEF/ODB/SPEF, infer timing paths, execute EDA tools,
create tasks, or use an autonomous multi-agent graph. Those capabilities need
new contracts and authoritative evidence first.

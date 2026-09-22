# Phase I capability matrix

| Capability | Current status | Provider | Example question | Evidence type | Future upgrade |
| --- | --- | --- | --- | --- | --- |
| Domain knowledge | supported | `EDACorpusKnowledgeProvider` | What is global routing? | cited QA/script row | broader curated documentation |
| Artifact discovery | supported | `LocalArtifactProvider` or execution adapter | What artifacts did routing produce? | artifact metadata | richer artifact indexes |
| Experiment state | supported | execution-foundation adapter | What is the routing status? | run/stage evidence | timeline and dependency views |
| Explicit metric | supported | execution-foundation adapter or local text search | What is run_02 routing WNS? | scoped metric evidence | registered metric families |
| Log/error evidence | supported | execution-foundation adapter or local text search | Show the routing error | bounded log excerpt | structured error taxonomy |
| Cross-run comparison | supported | execution-foundation adapter | Compare WNS across runs | aligned run-scoped metrics | explicit comparison policies |
| Design-object query | fixture-backed contract | `FixtureDesignDataProvider` / `UnavailableDesignDataProvider` | Where is instance u1? | typed design-object evidence | production data foundation |
| Timing analysis | fixture-backed contract | `FixtureAnalysisProvider` / `UnavailableAnalysisProvider` | What is the critical path slack? | scoped timing metric/path evidence | authoritative analysis service |
| Deep diagnosis | unavailable | no provider | Why did timing become worse? | insufficient without causal evidence | separate diagnosis contract |

## Provider boundaries

Knowledge and experiment evidence are separate sources. A managed run never
falls back to scanning a local attempt workspace. `LocalArtifactProvider` is
for an explicitly unmanaged workspace only. Every returned item is an
`Evidence` object with a locator and provider provenance.

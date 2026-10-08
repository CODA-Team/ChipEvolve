# Current capability matrix (0.2, 2026-10-08)

| Capability | Current status | Provider | Example question | Evidence type | Future upgrade |
| --- | --- | --- | --- | --- | --- |
| Domain knowledge | supported | `EDACorpusKnowledgeProvider` | What is global routing? | cited QA/script row | broader curated documentation |
| Artifact discovery | supported | `LocalArtifactProvider` or execution adapter | What artifacts did routing produce? | artifact metadata | richer artifact indexes |
| Experiment state | supported | execution-foundation adapter | What is the routing status? | run/stage evidence | timeline and dependency views |
| Explicit metric | supported | execution-foundation adapter or local text search | What is run_02 routing WNS? | scoped metric evidence | registered metric families |
| Log/error evidence | supported | execution-foundation adapter or local text search | Show the routing error | bounded log excerpt | structured error taxonomy |
| Cross-run comparison | supported | execution-foundation adapter | Compare WNS across runs | aligned run-scoped metrics | explicit comparison policies |
| Design-object query | exact instance/net/pin lookup connected; physical/relations fixture-only | `DataFoundationProvider` over installed SDK; fixtures for unconnected queries | Where is instance u1? | typed design-object evidence | production data foundation |
| Timing analysis | WNS/TNS and timing-path reads connected with source/units/corner gates | `DataFoundationProvider` over installed SDK | What is the critical path slack? | scoped timing metric/path evidence | authoritative analysis service |
| Deep diagnosis | fixture-backed contract | `FixtureDiagnosisProvider` / `UnavailableDiagnosisProvider` | Why did timing become worse? | evidence-linked finding with path and design support | authoritative diagnosis service |

## Provider boundaries

Knowledge and experiment evidence are separate sources. A managed run never
falls back to scanning a local attempt workspace. `LocalArtifactProvider` is
for an explicitly unmanaged workspace only. Every returned item is an
`Evidence` object with a locator and provider provenance.

Cross-run data metrics come from Data Foundation through DataExperimentProvider; execution lifecycle comes from EF. Current reasoning is deterministic evidence policy. No automatic supplementary analysis or autonomous diagnosis is implemented.

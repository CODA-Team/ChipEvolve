# Implementation Status

Current priority: independently released data-backed evidence and truthful comparison

Current slice: 0.2 SDK → Data Foundation → typed objects/timing/experiment evidence

Overall state: IN PROGRESS

## 2026-10-08 independently verified slice

- Public SDK wheel connects exact instance/net/pin identity, WNS/TNS and timing paths.
- DF owns snapshot resolution, object matching and canonical metric ownership.
- EF owns lifecycle; indexed data stages do not inherit control-stage names.
- Snapshot sources select artifacts without exposing another stage's inventory.
- Scope mismatch is FAILED; ambiguity, missing source/corner/unit is NEEDS_MORE_DATA.
- True import-linter configuration enforces 3 contracts (the inherited config ran 0).
- 87 tests, Ruff, format, strict Pyright and all 3 import contracts pass.
- Pure-wheel real Nangate45 STA comparison passes; root cause remains unsupported.

Not completed: typed relations/fanout/location/region, automatic supplementary
analysis, autonomous LLM diagnosis/optimization, complete PnR acceptance or
commercial-tool validation. Historical fixture milestones below do not fill
these gaps. Actual Codex paired observations live in ../admin/ACCEPTANCE_REPORT.md.

## Completed

- [x] Real managed-run discovery by design, including failed and active runs.
- [x] Exact registered-file lookup, bounded source excerpts, and verified binary download.
- [x] Run reports from official ORFS JSON metrics with direct artifact citations.
- [x] Explicit run record / registered file / direct excerpt / parsed metric levels.
- [x] Real ASAP7 GCD run `run-fd0b7130b99543db9d1b6292dae4e442`:
  112 artifacts, including 2 inputs, 43 results, 23 reports, and 35 logs.

- [x] Phase-I typed evidence, provider boundaries, and deterministic benchmark.
- [x] Managed-run evidence adapter uses only the execution foundation public API.
- [x] Baseline quality gate recorded below.
- [x] Frozen run/stage/artifact/metric/provenance context vocabulary.
- [x] `ExperimentContextProvider` port and execution-foundation adapter.
- [x] Explicit, latest-valid, current, and comparison selection policies.
- [x] Stage normalization, freshness assessment, partial-lineage handling, and
  deterministic conflict detection.
- [x] QueryTrace/QueryResponse context selection and conflict integration.
- [x] Phase-II benchmark: 9/9 deterministic fixture cases, including an
  aligned comparison that reports a deterministic difference.
- [x] Typed design-object vocabulary and `DesignDataProvider` port.
- [x] Fixture provider for instance/net/pin, location, connections, fanout,
  and region queries.
- [x] Query-service integration with cited design evidence and strict scope.
- [x] Phase-III-A benchmark: 8/8 deterministic fixture cases.
- [x] Typed timing-analysis vocabulary with explicit scope and provenance.
- [x] `AnalysisProvider` port for bounded WNS/TNS and timing-path reads.
- [x] Fixture and unavailable analysis adapters with strict missing-data
  behavior.
- [x] Query-service analysis intent, evidence conversion, citations, and
  partial-evidence refusal.
- [x] Phase-III-B benchmark: 5/5 deterministic fixture cases.
- [x] `DiagnosisProvider` port with typed, non-empty supporting evidence.
- [x] Fixture and unavailable diagnosis adapters with strict scope handling.
- [x] Root-cause QueryService integration that refuses unsupported or partial
  findings.
- [x] Phase-IV benchmark: 5/5 deterministic fixture cases.

## In progress

- [ ] Supplementary official report commands on a frozen source-run snapshot.
- [ ] Shared PDK/script dependency digests, historical recovery labels, pagination,
  and large-artifact streaming.
- [ ] Phase V action and optimization remains a separate future milestone.

## Baseline quality gate (2026-09-22)

- ruff check: PASS
- ruff format --check: PASS (126 files)
- pyright: PASS
- lint-imports: PASS (65 files, 184 dependencies)
- pytest: PASS (71 passed)
- Phase-II benchmark: PASS (9/9)
- Phase-III-A benchmark: PASS (8/8)
- Phase-III-B benchmark: PASS (5/5)
- Phase-IV benchmark: PASS (5/5)

## Next

1. Preserve the real managed-run acceptance path and earlier fixture benchmarks.
2. Add read-only, linked supplementary reporting through the execution foundation.
3. Fingerprint shared dependencies and add history/pagination semantics.
4. Keep autonomous diagnosis and repair outside this foundation slice.

## Known issues

- The execution-foundation protocol is still documented as v1alpha1; the
  adapter must remain tolerant of optional fields and preserve partial status.
- Legacy runs retain their old, incomplete artifact inventories.
- Reported timing/area/power numbers retain the source's raw values; units and
  corners are not yet normalized across platforms.
- Design-object diagnosis and repair remain fixture-backed and are not claimed
  as production OpenROAD capabilities.

## Architectural decisions

- ADR-008 records the Phase-II context provider and selection-policy boundary.
- ADR-009 records the typed read-only design-data boundary.
- ADR-010 records the bounded timing-analysis provider boundary.
- ADR-011 records the evidence-linked diagnosis provider boundary.

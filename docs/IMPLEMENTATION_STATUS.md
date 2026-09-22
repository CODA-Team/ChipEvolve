# Implementation Status

Current phase: Phase IV — Evidence-Grounded Diagnosis

Current slice: 4.1 — evidence-linked diagnostic findings complete

Overall state: COMPLETE

## Completed

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

- [ ] Phase V explicit reversible action and optimization (future milestone).

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

1. Preserve the Phase-II, Phase-III-A, Phase-III-B, and Phase-IV benchmarks.
2. Add diagnosis comparison only with explicit support and conflict semantics.
3. Keep action work behind new ports; do not widen diagnosis into execution
   controls or autonomous repair.

## Known issues

- The execution-foundation protocol is still documented as v1alpha1; the
  adapter must remain tolerant of optional fields and preserve partial status.
- No external OpenROAD experiment is used by the deterministic benchmark.

## Architectural decisions

- ADR-008 records the Phase-II context provider and selection-policy boundary.
- ADR-009 records the typed read-only design-data boundary.
- ADR-010 records the bounded timing-analysis provider boundary.
- ADR-011 records the evidence-linked diagnosis provider boundary.

# Execution-foundation integration boundary

This document records the inspection of the sibling repository
`/home/wjyuan/execution foundation` on 2026-09-21. No file in that repository
was changed for this Query Agent work.

## Observed API and models

The following modules were read:

- `README.md` and `docs/ARCHITECTURE_OVERVIEW.md`: the foundation owns
  execution intent translation, attempt workspaces, process supervision,
  lifecycle, artifact/metric/log evidence, and provenance; external Toolkit
  adapters are processes rather than imported Python plugins.
- `contracts/src/openroad_platform_contracts/task.py`: `TaskSpec`,
  `RuntimeRequirements`, `PluginManifest`, and `PluginResult`.
- `contracts/src/openroad_platform_contracts/artifact.py`: `ArtifactDeclaration`,
  `Artifact`, and `Metric`.
- `contracts/src/openroad_platform_contracts/runtime.py`: `RuntimeStatus`,
  `AttemptStatus`, `Failure`, and `Event`.
- `core/runtime/src/openroad_platform_runtime/store.py`: `RunRecord`,
  `StageRun`, `Attempt`, `RuntimeStore`, lifecycle transitions, artifact and
  metric registration, event recording, and durable state.
- `core/runtime/src/openroad_platform_runtime/runtime.py`:
  `WorkflowRuntime.submit`, `execute_once`, `describe`, and bounded artifact
  excerpt access.
- `core/runtime/src/openroad_platform_runtime/artifact_inventory.py`,
  `log_query.py`, and `resource_query.py`: read views for registered artifacts,
  bounded logs, and resource/status observations.
- `core/provenance/src/openroad_platform_provenance/index.py`:
  `EvidenceIndex.runs`, `run_detail`, `metrics`, `artifacts`, `timeline`, and
  `artifact_graph`, including metric-to-artifact lineage.
- `core/client/src/openroad_platform_client/client.py`: the public HTTP
  `KernelClient` for health, plugin catalogue, input upload, run submission,
  run detail, metrics, artifacts, timeline, resources, logs, bounded artifact
  excerpts, and graph queries.
- `gateway/src/openroad_platform_gateway/kernel_api.py` and `router.py`: the
  HTTP translation/authentication layer for those routes.
- `docs/PLUGIN_PROTOCOL.human.md` and `plugins/example/adapter.py`: the
  external-process request/result protocol and manifest-based Toolkit boundary.
- `tests/core/test_runtime.py`, `test_store.py`, and `test_provenance.py`:
  lifecycle, persistence, bounded evidence and lineage behaviour.

The execution protocol is documented as `v1alpha1` and is not yet a frozen
compatibility contract. The kernel deliberately keeps domain parameters opaque
and does not provide an EDA object graph.

## Answers to the integration questions

### 1. Stable interface for future execution requests

The Query Agent should define its own `AnalysisProvider` port and, in a later
phase, implement an adapter that speaks the foundation's public HTTP API. The
adapter would submit a typed, read-only analysis request as a `TaskSpec`, retain
the returned `run_id`, poll run status, then map metrics, artifacts, logs and
artifact excerpts into Query Agent `Evidence`.

Phase I.1 implements `RunEvidenceProvider` and
`ExecutionFoundationRunEvidenceAdapter` for existing evidence. It does not
submit analysis tasks. The adapter consumes only the public `KernelClient`
surface through a narrow adapter-local protocol, and maps responses to Query
Agent `Evidence` with run/stage scope, artifact IDs, hashes, locators, metric
parser metadata, timestamps, logs, timeline and graph provenance.

`AnalysisProvider` remains a future request boundary and returns
`NEEDS_MORE_DATA` when a new analysis capability is required.

### 2. Existing objects

The foundation has all of the execution concepts needed at its own boundary:

| Concept | Observed representation |
| --- | --- |
| Task | `TaskSpec` contract |
| Run ID | `RuntimeStore`/HTTP run response `run_id` |
| Stage | `StageRun` and run-detail `stages` |
| Attempt | `Attempt` with status, worker and workspace |
| Workspace | per-attempt workspace path owned by runtime |
| Artifact | hashed `Artifact` plus API artifact views |
| Metric | `Metric` with optional source artifact and parser lineage |
| Logs/status | `LogQuery`, `RuntimeStatus`, `AttemptStatus`, timeline/events |
| Provenance | `EvidenceIndex` and artifact/metric lineage |

The Query Agent should not duplicate lifecycle objects. Its `QueryContext` only
uses the identifiers needed to scope a question (`workspace`, optional
`design_id`, `run_id`, `stage`) plus an explicit `source` distinguishing a
local unmanaged workspace from a managed run.

### 3. Shared versus independent semantics

Query Agent may use the meanings of `run_id`, `stage`, artifact, metric,
workspace and provenance when citing execution evidence. It must keep its own
`Evidence`, `EvidenceScope`, `EvidenceLocator`, `EvidenceProvenance`, query
plans and answerability states: those describe reasoning coverage, not process
lifecycle. A foundation metric becomes Query Agent evidence only after the
adapter preserves its source, scope and lineage.

### 4. Direct Python import or service boundary?

Use a service boundary. The foundation's HTTP `KernelClient` is the observed
public client, while its runtime/store packages are kernel implementation and
database owners. Query Agent domain/application code must never import
`openroad_platform_runtime`, open the SQLite state root, or import a Toolkit
adapter. If a composition root chooses to reuse the client package, that
choice must stay inside `adapters/run_evidence/` and remain replaceable by a
wire client; no application code should depend on it.

### 5. Avoiding duplicated execution responsibilities

The future analysis adapter sends an analysis intent and parameters to the
foundation. It does not create workspaces, launch subprocesses, allocate
resources, manage task state, copy/register artifacts, collect logs, or write
provenance. It waits for the foundation's run result and translates its
read-only views into evidence. The current `LocalArtifactProvider` is for a
workspace explicitly supplied to Query Agent; it is not a second execution
workspace manager. A managed context cannot carry an attempt workspace, and
`LocalArtifactProvider` rejects managed contexts, so registered execution
artifacts and transient filesystem contents cannot become competing sources of
truth.

## Recommended future request flow

```text
QueryService -> AnalysisProvider port
             -> execution-foundation adapter
             -> POST /kernel/runs (read-only analysis TaskSpec)
             -> GET run/status + metrics/artifacts/logs/excerpts
             -> typed Query Agent Evidence
```

The adapter must reject analysis requests that would mutate the design, and it
must preserve `run_id`, stage, artifact IDs, SHA-256, parser metadata and
source locators in provenance.

## Open questions

1. Which foundation Toolkit capability names and task parameter schemas will be
   admitted for `report_timing`, `report_power`, and `report_design_area`?
2. Will a stable, versioned API expose remote artifact bytes/excerpts without
   exposing attempt workspace paths?
3. How will Query Agent authenticate and authorize analysis requests, and how
   will it associate a query's design identity with a foundation `TaskSpec`?
4. Which artifact/metric schema fields are guaranteed across the current
   `v1alpha1` protocol transition?

# ADR-007: Managed Runs Use execution-foundation Evidence

## Context

An execution-foundation run has registered artifacts, metrics, logs and
provenance. Its attempt workspace may contain temporary, stale or unregistered
files.

## Decision

`QueryContext` distinguishes `MANAGED_RUN` from `LOCAL_WORKSPACE`. Managed runs
must use `RunEvidenceProvider` and the public execution-foundation read API.
`LocalArtifactProvider` is only for explicitly supplied unmanaged workspaces and
rejects managed contexts.

## Consequences

There is one authoritative evidence world for managed runs. Query Agent does
not open the foundation database, scan attempt workspaces, or duplicate
artifact/lifecycle management. New analysis remains a separate future
`AnalysisProvider` concern.

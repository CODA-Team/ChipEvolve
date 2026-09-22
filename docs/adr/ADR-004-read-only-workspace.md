# ADR-004: Phase-I Workspace Access Is Read-Only

## Context

The Query Agent observes existing runs and artifacts. Execution and mutation
belong to the execution foundation.

## Decision

`LocalArtifactProvider` exposes list, find, search, bounded excerpt and stat
only. It rejects traversal, symlink escapes, binary text reads and oversized
reads; it has no shell or write operation.

## Consequences

Artifact discovery is safe to run against a real workspace and easy to
contract-test. Any future mutation must be an explicitly reviewed execution
capability, not an accidental provider method.

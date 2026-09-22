# ADR-002: Evidence Is First-Class Domain Data

## Context

Answers about physical design must be traceable to an artifact, knowledge
source, or structured data record.

## Decision

Every provider returns typed `Evidence` with scope, locator and provenance.
Answers cite those evidence items; untraceable strings are not evidence.

## Consequences

The response pipeline can audit claims and report conflicts or partial coverage.
Adapters do a little more work to preserve lineage, and domain models remain
explicit rather than accepting arbitrary dictionaries.

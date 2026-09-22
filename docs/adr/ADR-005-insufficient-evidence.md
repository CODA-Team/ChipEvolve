# ADR-005: Insufficient Evidence Is a Valid Business Result

## Context

Root-cause and relationship questions often exceed Phase I evidence and
capabilities.

## Decision

Return `NEEDS_MORE_DATA` with current evidence, missing requirements, missing
capabilities and next steps. Do not throw an exception or invent a cause.

## Consequences

Callers can request the next useful observation and distinguish unavailable
capability from a failed service. A response may be less satisfying, but it is
honest and auditable.

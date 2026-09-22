# Phase III-A — Design Object Understanding

## Scope

This slice answers the structural questions “what exists?”, “where is it?”,
and “what is connected?” through a typed, read-only `DesignDataProvider`.
Supported operations are instance/net/pin lookup, location, connections,
fanout, and instances-in-region.

## Boundary

The domain exposes immutable references and small summaries. Providers translate
OpenDB, DEF, or another data foundation into those models; no parser, SDK,
filesystem path, or mutable provider dictionary enters the application. The
fixture adapter is only a deterministic contract implementation for tests and
does not represent external EDA accuracy.

## Answerability

An unknown object, wrong design scope, or unavailable provider yields
`NEEDS_MORE_DATA` with no fabricated object. Returned evidence retains a design
locator and optional source hash, and is visible in `QueryTrace`.

## Deferred work

Timing paths, cell delay, parasitics, congestion, DRC, power, diagnosis, and
write/ECO actions belong to later analysis/action contracts. They must not be
added as fields to these structural objects merely to make one query pass.

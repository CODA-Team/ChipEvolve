# Prompt For External CPU LEGALM Implementer

You are implementing a high-performance CPU detailed-placement legalizer using
LEGALM/ALM-style ideas as a standalone reference implementation.

For this reference deliverable, do not integrate with OpenROAD directly and do
not make the implementation depend on OpenROAD classes. The output should be
clean algorithm code that can be studied, benchmarked, and later ported into
another framework or wrapped by a separate integration layer.

## Goal

Implement a robust CPU legalizer that accepts the data model in `DATA_MODEL.md`
and returns a complete placement result plus telemetry.

The algorithm should target modern standard-cell legalization with mixed-height
cells, fixed blockages, row/fence regions, weighted nets, and high utilization
cases.

## Suggested Algorithm Shape

Use a staged architecture unless you can justify a better one with telemetry.
The exact objective terms, candidate sets, and stage ordering are open design
choices.

1. **Relaxed guidance stage**
   - Project cells to legal static sites or good target regions.
   - Movable-cell overlaps may remain.
   - Optimize displacement and optional HPWL proxy.

2. **Capacity / overflow removal stage**
   - Prefer row segments as the capacity model.
   - Use ALM/BGD, auction, min-cost assignment on bounded buckets, or another
     scalable overlap-removal method.
   - Scarce cells, wide cells, multi-row cells, and cells with few candidate
     segments should be handled early.

3. **No-overflow refinement stage**
   - Preserve legality.
   - Improve displacement and HPWL proxy with bounded local moves.
   - Do not increase max displacement tail without explicit telemetry.

4. **Failure-aware repair**
   - If full legalization cannot finish, return a `NearLegal` result and clear
     telemetry explaining unresolved overlaps, candidate-cap hits, and runtime
     limits.

## Performance Requirements And Guardrails

- CPU only.
- Use up to `max_threads`; do not spawn unbounded threads.
- Deterministic mode must produce repeatable output.
- Avoid full-cell-pair enumeration.
- Avoid full-grid scans in inner loops.
- Keep candidate generation bounded.
- High-fanout nets should be skipped, approximated, or cached.
- Use row/segment indexing instead of repeatedly scanning all rows.

AES is only a smoke test.  JPEG is the first serious gate.  The implementation
should be designed for larger cases from the beginning.

## Data Structures To Use Or Adapt

Use or adapt the structures in `DATA_MODEL.md`:

- `Rect`
- `Row`
- `Segment`
- `Cell`
- `Pin`
- `Net`
- `LegalizationProblem`
- `LegalizationOptions`
- `LegalizationResult`
- `LegalizationTelemetry`

You may add internal structures such as:

- `RowSegmentIndex`
- `CellCandidate`
- `BucketAssignment`
- `NetBBoxCache`
- `OverflowGrid`
- `AlmMultiplier`
- `MoveTransaction`

## Expected Deliverables

Please provide:

1. A standalone C++17 or newer implementation.
2. Unit tests for:
   - one-row simple legalization,
   - fixed blockage avoidance,
   - multi-row cell placement,
   - high-fanout net skip/cache behavior,
   - deterministic repeatability.
3. A small benchmark driver that reads a simple JSON or text form of the data
   model and writes placements plus telemetry.
4. A README explaining:
   - algorithm stages,
   - time complexity,
   - parallel regions,
   - known failure modes,
   - tuning parameters.
5. Benchmark logs for at least:
   - `aes_nangate45`,
   - `jpeg_nangate45`.

## Success Criteria

The first version does not need to beat OpenROAD diamond on every metric. It
should be:

- robust,
- fast enough to run JPEG without pathological slowdown,
- deterministic,
- well-instrumented,
- structurally capable of later case-specific tuning.

The most valuable result is a clear implementation where we can see why a case
succeeds or fails and which stage should be improved next.

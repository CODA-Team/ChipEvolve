# Design Data Foundation

Independent application. One process, one database, one deterministic query API.

- Imports permitted: `openroad_platform_contracts`, `openroad_platform_client` only (G3, G4).
- It must never open a kernel database directly (G5).
- Smoke: `python3 apps/data_foundation/smoke.py`

## Why this app exists

This service turns a parser-produced snapshot into a queryable design context.
It owns snapshot boundaries, object identity inside a snapshot, timing-path
expansion, physical context, and source-location references. The original EDA
files remain in the execution foundation and are reached by their artifact
identity.

When a run bundle is imported, the service carries forward the run's
registered non-runtime artifacts as `source_artifacts`. Parser evidence may
refer to a source by its role and logical path before the execution foundation
assigns its final identity; the query layer resolves that reference only
against this registered catalogue. The service never reconstructs a host path
from a filename.

The portable input is the `query-data` directory described by the team design:
`manifest.json`, `artifacts.jsonl`, `objects.jsonl`, `relations.jsonl`,
`timing_paths.jsonl`, `timing_points.jsonl`, `markers.jsonl`, and
`coverage.json`. It can also import a verified run bundle through
`POST /snapshots/from-run` when started with `--kernel-url`.

The request/response shape is recorded in `snapshot.schema.json`. This is the
replaceable service contract; clients do not import this app's storage code.

Native data production is kept outside this process in the `openroad-data`
capability. Its OpenDB, OpenSTA, and ORFS paths produce the same portable
snapshot directory, so the index and API do not change when an extractor is
replaced.

Geometry is carried as typed records (`rect`, `polygon`, `wire_segment`,
`via`, and related forms); a via keeps cut/lower/upper layers instead of being
treated as a rectangle. Rule observations retain whether they were parsed,
supported, partial, violated, or unknown.

The API deliberately follows IDs returned by the snapshot. It never guesses a
file path, parses an arbitrary host directory, or asks a language model to
infer a relationship.

During registration, parser evidence that has only an artifact role and
logical location is resolved against the snapshot's registered artifact
catalogue. An exact logical-path match wins; otherwise a single role/stage
candidate is accepted. Zero or multiple candidates remain explicitly
`unresolved` or `ambiguous`, so a query can never silently attach evidence to
the wrong raw file.

Each indexed entity keeps three identity views: the native identity supplied by
the adapter, the snapshot-local object ID used by stored relations, and a
scoped canonical identity containing design, revision, kind, and hierarchical
name. Timing points and physical observations carry references to that identity
without replacing their native IDs. An ambiguous canonical identity is
rejected at snapshot registration; records are never silently merged.

Cross-stage comparison is intentionally strict: it requires the same design,
revision, path identity, and timing unit. Incompatible snapshots are rejected
with an explicit reason instead of receiving a misleading numeric delta.
When both snapshots carry canonical object identities, the comparison returns
explicit `same_design_object_as` relations and uses those identities for
physical deltas; it falls back to snapshot-local IDs only for older records
that have no canonical identity.

Useful endpoints:

- `GET /snapshots?design_id=...` lists immutable fact boundaries.
- `GET /runs/{run_id}/summary` returns all indexed stage snapshots for one run.
- `GET /runs/{run_id}/metrics?stage=...&name=...&scene=...` returns structured
  metric observations across that run's snapshots.
- `GET /snapshots/{id}/timing-paths` lists path summaries.
- `GET /snapshots/{id}/observations?name=...&kind=...` lists indexed facts.
- `GET /snapshots/{id}/timing-paths/{path}/points` expands ordered points.
- `GET /snapshots/{id}/objects/{object}` returns entity, observations, and relations.
- `GET /snapshots/{id}/objects/{object}/context` returns one object's connected
  entities, physical facts, and source references.
- `GET /snapshots/{id}/nets?name=...` resolves one exact indexed net name;
  multiple matches are returned for the caller to reject rather than guessed.
- `GET /snapshots/{id}/physical/{object}` returns typed geometry/routing context.
- `GET /snapshots/{id}/nets/{net}/context` returns connectivity, route facts,
  and source references for one net.
- `GET /snapshots/{id}/evidence?artifact_id=...` returns source locations.

## What it must not do

It does not own execution lifecycle, raw artifact storage, design diagnosis,
repair, or a second design database. Native parser capabilities are external
producers: their output is converted into this portable snapshot contract.

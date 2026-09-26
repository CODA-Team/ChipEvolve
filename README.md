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

Useful endpoints:

- `GET /snapshots?design_id=...` lists immutable fact boundaries.
- `GET /snapshots/{id}/timing-paths` lists path summaries.
- `GET /snapshots/{id}/timing-paths/{path}/points` expands ordered points.
- `GET /snapshots/{id}/objects/{object}` returns entity, observations, and relations.
- `GET /snapshots/{id}/objects/{object}/context` returns one object's connected
  entities, physical facts, and source references.
- `GET /snapshots/{id}/physical/{object}` returns typed geometry/routing context.
- `GET /snapshots/{id}/nets/{net}/context` returns connectivity, route facts,
  and source references for one net.
- `GET /snapshots/{id}/evidence?artifact_id=...` returns source locations.

## What it must not do

It does not own execution lifecycle, raw artifact storage, design diagnosis,
repair, or a second design database. Native parser capabilities are external
producers: their output is converted into this portable snapshot contract.

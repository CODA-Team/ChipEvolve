# netaware14_rowedge_shortlist_hpwl

Artifact kind: `generator_delta`.

This is the clean/generator-ready specification for the next net-aware
standalone base. It is not a clean-base patch and not an overlay chain. The
current runnable harness entry named `netaware14_rowedge_shortlist_hpwl` is only
a bring-up alias over `netaware03_row_guard_frontier`; do not treat that build
as algorithm evidence for this mechanism.

## Design Intent

Build the candidate frontier cheaply first, then spend local net traversal only
on a small bounded shortlist:

- Cheap NBLG frontier first: `current_blend` target cost, `history_runtime_trim`
  congestion cost, and normal NBLG DRC/history scoring before any local HPWL.
- Cached bounded local HPWL secondary ranking: rank the cheap frontier by base
  cost, evaluate `localHpwlDeltaCost` only for eligible shortlist entries, and
  cache per `(cell_idx, x, y)` candidate inside `findBestLocation`.
- Row-edge shortlist probes: include row-edge probes as bounded frontier
  candidates, but keep midpoint/connectivity anchors fallback-only unless the
  cheap frontier is empty.
- Telemetry: count candidate frontier size, shortlist HPWL evaluations, fanout
  skips, displacement-guard rejects, row-edge probe accepts, and fallback-anchor
  uses.

## Relationship To Previous Artifacts

- `netaware12_prefilter_hotset_guard` remains the current best repair evidence,
  but it is an overlay over the netaware11 parent, not a hard standalone base.
- R5 `netaware13_quality_recover_r5` is not promoted: it recovered some HPWL,
  but the completed evidence crossed AES runtime and JPEG max-displacement
  limits, and the tightened rebuild has no post-tightening eval JSON.
- R6/base-bringup `netaware14_rowedge_shortlist_hpwl` built as a harness alias
  using `netaware03_row_guard_frontier`; that result validates plumbing only.

## Generator Contract

The intended implementation belongs in the family mutation generator, not as a
manual overlay patch:

- Source family: `clean_evolve_base`.
- Touched files: `src/NegotiationLegalizer.h` and
  `src/NegotiationLegalizerPass.cpp`.
- Entrypoint contract: `detailed_placement_evolve -use_negotiation`.
- Required new helper split: `negotiationBaseCost(...)` for cheap scoring and
  `negotiationCost(...)` as `base + localHpwlDeltaCost` only where needed.
- Required eligibility: low/medium-fanout cells, displacement-hot cells, or
  late-unsettled illegal cells.

See `generator_deltas/netaware14_rowedge_shortlist_hpwl.yaml` for the concrete
mutation recipe.

## Required Gates Before Promotion

Run a private materialized build and strict same-run baseline comparisons on:

- `aes_nangate45`
- `jpeg_nangate45`
- `ariane133_nangate45`

Reject if AES/JPEG/ariane runtime exceeds about +20%, if JPEG max displacement
grows materially, or if HPWL improvement is only isolated to one small case.
Only after those pass, run `bp_quad_nangate45` as a two-stage stress gate:
legalizer return first, then full metrics completion.

## Current Blockers

- No generator mutation body is committed yet; shared scripts were intentionally
  not edited in this Worker B scope.
- No clean-base patch exists yet. The only code patch in
  `netaware_objective/research_patches` is an overlay from netaware11 to
  netaware12.
- Existing R6/base-bringup evidence is an alias result and must not be promoted
  as this algorithm.

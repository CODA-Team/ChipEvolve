# Priority Escape Family Observations (2026-04-22)

## Family

- id: `priority_escape`
- parent: `localized_swap`
- intent:
  - improve large-case `HPWL / WNS / TNS` together
  - act earlier in the main negotiation pass instead of relying only on postopt
  - selectively give critical cells a stronger escape path

## Code surfaces

- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.h`
- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizerPass.cpp`

## Mechanisms

- critical-first negotiation ordering
  - cells with higher pin count or larger displacement are processed earlier
  - this changes the main-pass legalization dynamics, not just postopt
- deduplicated candidate visitation
  - avoids re-evaluating the same `(x, y)` candidate from overlapping windows
- critical-cell escape expansion
  - for high-pin / high-displacement cells after the isolation point, the solver
    explores a coarser wider escape window around the midpoint between current
    and initial locations
- diamond-seeded escape candidate generation
  - diamond search is used as a candidate generator inside `findBestLocation`
    for critical cells, rather than waiting for whole-design stall recovery

## Representative result

Case: `ariane133_nangate45`

Compared against `localized_swap`:

- `HPWL delta micron`: `-32219.902 -> -32464.642`
- `setup_ws`: `-0.579907 -> -0.572170`
- `setup_tns`: `-1210.03 -> -1182.09`
- `runtime_seconds`: `129.928 -> 131.326`

Compared against baseline negotiation:

- `HPWL delta micron`: `96300.188 -> -32464.642`
- `setup_ws`: `-0.577436 -> -0.572170`
- `setup_tns`: `-1191.57 -> -1182.09`
- `runtime_seconds`: `80.236 -> 131.326`

Case: `jpeg_nangate45`

Compared against baseline negotiation:

- `HPWL delta micron`: `164045.8655 -> 141918.8655`
- `setup_ws`: `-0.130415 -> -0.199956`
- `setup_tns`: `-49.8277 -> -58.3203`
- `runtime_seconds`: `34.667 -> 52.414`

Compared against older heavy evolve family `sweep_jpeg_n45_evolve_retry`:

- `HPWL delta micron`: `63849.0555 -> 141918.8655` (worse)
- `setup_ws`: `-0.118497 -> -0.199956` (worse)
- `setup_tns`: `-41.3098 -> -58.3203` (worse)
- `runtime_seconds`: `511.864 -> 52.414` (much better)

## Interpretation

- This family is the first stacked variant after `localized_swap` that
  improved all three primary quality metrics (`HPWL`, `WNS`, `TNS`) on
  `ariane133`.
- On `jpeg_nangate45`, it behaves more like a runtime-controlled escape
  family: it keeps a baseline HPWL gain and dramatically cuts runtime versus
  the older heavy evolve family, but it does not improve setup timing there.
- The runtime penalty versus `localized_swap` is present but modest compared to
  the large quality gain retained from the family stack.
- This is still a meaningful direction for larger-case evolution because the
  gains come from main-pass behavior, not just wider postopt, but it should be
  treated as a base for further timing-aware stacking rather than a final
  promoted large-case family.

## Current status

- keep in active target-plane code
- preserve as reusable stack component in `family_components/priority_escape.yaml`
- use as a base for timing-aware follow-on families
- continue validating on additional larger non-macro cases before promoting it
  to the default large-case base

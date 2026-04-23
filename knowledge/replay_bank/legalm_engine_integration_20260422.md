# LEGALM Engine Regime Note

`legalm_engine` is a family-specific `dpl_evolve` variant.

Use it through:

- `evolve_agent/family_variants/legalm_engine/manifest.yaml`
- `evolve_agent/family_variants/legalm_engine/dpl_evolve.patch`
- `evolve_agent/scripts/materialize_family_variant.sh`

Build it into a dedicated OpenROAD binary, then run it as:

- the clean `evolve_line`
- with the `legalm_engine` family variant binary
- on the `strict` legalization-only track

## Current role

Treat `legalm_engine` as:

- a structurally different initializer from negotiation
- a Stage1/Stage2/Stage3 base for direct legalizer evolution
- a medium-case initial family when runtime needs to stay comparable

Do not treat it as part of the clean main-tree base.

## Current implementation shape

Promoted structure:

- `Stage1` local scanline-style initializer around original positions
- `Stage2` ALM legalization with partition refresh and local-optimum escape
- `Stage3` bounded local net-aware refinement
- `improvePlacementLite` as a light post-refine
- fast unconstrained-cell legality checks with exact overflow recomputation kept
  for convergence safety

## Current comparable regime

### `gcd_nangate45`

- result: strict smoke pass
- `hpwl_delta_micron = 651.2265`
- `setup_ws = 0.0124074`
- `setup_tns = 0`
- `runtime_seconds = 2.886`

Interpretation:

- the variant binary and strict evolve flow work end-to-end

### `aes_nangate45`

baseline:

- `runtime_seconds = 9.398`
- `hpwl_delta_micron = 856.1465`
- `setup_ws = -0.0170307`
- `setup_tns = -0.0702634`

`legalm_aes_n45_20260423_rt6`:

- `runtime_seconds = 8.432`
- `hpwl_delta_micron = 1033.7915`
- `setup_ws = -0.014014`
- `setup_tns = -0.0777443`

Interpretation:

- runtime is already at or below baseline
- setup WNS is better than baseline
- HPWL is comparable but still trails baseline
- setup TNS still needs improvement

### `ibex_nangate45`

baseline:

- `runtime_seconds = 9.356`
- `hpwl_delta_micron = 7159.3705`
- `setup_ws = 0.016064`
- `setup_tns = 0`

`legalm_ibex_n45_20260423_rt6`:

- `runtime_seconds = 10.686`
- `hpwl_delta_micron = 9776.1105`
- `setup_ws = 0.0216451`
- `setup_tns = 0`

Interpretation:

- runtime is close to baseline
- setup WNS is better than baseline
- HPWL still needs work

## Use it when

- the case is medium-scale and stdcell-only
- a different initializer is worth trying before negotiation-family patching
- direct Stage1/Stage2/Stage3 evolution is more promising than another
  negotiation tweak

## Current gates

Promote follow-on `LEGALM` families only when they keep:

- runtime in the same regime as the current medium-case path
- legality success on `gcd`, `aes`, and `ibex`
- comparable or better HPWL
- comparable or better setup WNS/TNS

## Next directions

Prefer:

- Stage2 overflow escape quality
- Stage3 zero-overflow refinement quality
- HPWL/TNS improvement without giving back the current runtime regime

Avoid:

- widening search globally just to gain quality
- reintroducing family-specific code into the clean main-tree base

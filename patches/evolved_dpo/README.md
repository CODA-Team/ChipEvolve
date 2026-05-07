# Evolved DPO / Improve-Placement Patches

This directory preserves source-root patches for DPO/improve-placement donor
mechanisms. These patches are intended for a private `dpl_evolve` source tree,
not for the OpenROAD repository root.

Apply base:

- Run `scripts/prepare_workspace.sh` first, or otherwise materialize a private
  `dpl_evolve` source tree from the current framework/evolved legalizer seeds.
- In Teacher/Student rounds, prefer generated local start branches such as
  `start/evolved_legalm_dpo_neg017b` or the generated
  `07_apply_evolved_dpo_patch.sh --check-only` helper. Do not ask Students to
  hand-write `git apply` commands.

The source-root patch base is the common `src/Optdp.cpp` used by the current
framework/evolved legalizer seeds in the cross-ablation workspace. It was
verified with `git apply --check` against that source root.

## Patch Inventory

| patch | apply base | mechanism id | meaning | use when |
|---|---|---|---|---|
| `src_dpo_neg014_hybrid_quality.patch` | source-root framework/evolved legalizer seed | `neg014_hybrid_quality` | highest-quality transferable DPO donor | final HPWL is primary |
| `src_dpo_neg015_staged_runtime.patch` | source-root framework/evolved legalizer seed | `neg015_staged_runtime` | runtime-balanced staged fallback variant | runtime is constrained |
| `src_dpo_neg017b_algo1_src_cache_runtime.patch` | source-root framework/evolved legalizer seed | `neg017b_algo1_src_cache_runtime` | recommended runtime-quality donor with source-edge cached Algorithm-1 scoring | default first try when both quality and runtime matter |
| `src_dpo_neg014_to_neg015_runtime_delta.patch` | source root after `src_dpo_neg014_hybrid_quality.patch` | `neg014_to_neg015_runtime_delta` | review/port delta from quality donor to staged runtime donor | building a runtime repair |
| `src_dpo_neg015_to_neg017b_algo1_cache_delta.patch` | source root after `src_dpo_neg015_staged_runtime.patch` | `neg015_to_neg017b_algo1_cache_delta` | review/port delta adding parallel scoring, top-K telemetry, and source-edge cache | upgrading a staged-runtime donor without rereading the full patch |

## Mechanism Summary

### NEG014 hybrid quality donor

Core mechanism:

- Algorithm 1 median optimal-region kick selection.
- Algorithm 2 local DP repair around kicked rows.
- Algorithm 3 transaction accept/rollback with fallback detailed descent.

Cross-legalizer evidence:

- Wins 9/9 over same-legalizer base in the three-legalizer by three-case
  cross-ablation.
- Mean final HPWL delta versus same-legalizer base: about `-15151.1 um`.
- Strongest observed pairings: `diamond + neg014_hybrid` for medium/dense
  image-style cases, `legalm + neg014_hybrid` for large row-rich wrapper-style
  cases.

Cost:

- Runtime can be 3x or more over base because each LSMC transaction may run
  fallback descent.

### NEG015 staged runtime donor

Core mechanism:

- Keeps NEG014's Algorithm 1/2/3 structure.
- Replaces always-full fallback with staged fallback:
  `cheap gs/vs -> forward reorder if needed -> reverse reorder if still needed`.
- Adds explicit fallback telemetry.

Evidence:

- In the negotiation line, runtime changed versus NEG014 by roughly:
  - medium dense: `-33.3%`, final HPWL also improved slightly,
  - dense image-style: `-58.0%`, final HPWL regressed by about `+1908.7 um`,
  - large row-rich: `-11.4%`, final HPWL regressed by about `+1127.0 um`.

Use this patch as a runtime-balanced donor or as the base for a follow-up 016
that restores high-ROI reorder fallback without returning to full repeated
fallback descent.

### NEG017b Algo1 source-cache runtime-quality donor

Core mechanism:

- Keeps the NEG015 staged fallback policy and the NEG016 safe parallel search
  boundary.
- Scores Algorithm-1 region-kick candidates with OpenMP dry-run scoring and
  `partial_sort` top-K exact reduction.
- Adds a source-cell incident-edge cache for dry-run HPWL scoring. Current HPWL
  and source outside extrema are cached per source batch; destination-only nets
  are scored on the fly with thread-local scratch.
- Leaves exact `trySwap`, journal validation, legality, commit, and rollback
  serial and deterministic.

Formal three-case evidence versus NEG016:

- Medium dense: same final HPWL, runtime about `-3.9%`.
- Dense image-style: same final HPWL, runtime about `-4.1%`.
- Large row-rich: same final HPWL, runtime about `-6.6%`.

Tradeoff:

- This is the recommended runtime-quality donor because it keeps the 015/016
  HPWL while reducing runtime.
- It does not recover the maximum final HPWL of NEG014 on dense image-style and
  large row-rich cases. When maximum HPWL quality is primary, use NEG014 first
  or evolve a selective high-ROI fallback on top of NEG017b.

## Agent Use Rules

- These patches modify improve placement only through `src/Optdp.cpp`. They do
  not replace the legalizer seed.
- Always evaluate on the active case after applying. A donor that transfers in
  the matrix is still only a candidate for a new design.
- Report canonical `metrics.json:hpwl_stages`, runtime, avg/max displacement,
  legality, and DPL fallback/kernel logs.
- Do not stack multiple DPO patches blindly. Choose one donor, evaluate, then
  evolve from the measured result. A practical default is NEG017b for balanced
  quality/runtime and NEG014 for quality-ceiling exploration.

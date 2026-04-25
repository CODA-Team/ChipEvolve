# netaware_objective Hardening Summary, 2026-04-25

Scope: analyze `netaware12`, `netaware13`, and algobank evidence, then package
the best currently usable net-aware state without modifying ORFS or OpenROAD
tracked files.

## Current Artifact

Packaged artifact:
`family_variants/netaware_objective/`

Packaged state:
`netaware12_prefilter_hotset_guard`

Patch basis:
`netaware11_local_hpwl_anchor_cap -> netaware12_prefilter_hotset_guard`

Light check performed:

```bash
patch --dry-run -p1 -d <backed-up-netaware11-source> \
  < family_variants/netaware_objective/dpl_evolve.patch
```

Result: pass on `src/NegotiationLegalizer.h` and
`src/NegotiationLegalizerPass.cpp`.

## Evidence Read

Netaware evidence:

- R3/R1 `netaware11_local_hpwl_anchor_cap`: strong quality signal, but not base.
  AES HPWL improved -22.47% and JPEG -13.23%, but runtime was +113.07% on AES
  and +43.17% on JPEG; JPEG max displacement was +74.62%.
- R4 `netaware12_prefilter_hotset_guard`: current best repair candidate. AES,
  JPEG, and ariane are legal. HPWL deltas improved -2.07%, -6.47%, and -4.58%;
  runtime overheads were +17.65%, +17.87%, and +20.20%; JPEG max displacement
  was only +0.92%.
- R5 `netaware13_quality_recover_r5`: not promoted. Initial evidence improved
  AES/JPEG HPWL to -3.09% and -7.25%, but AES runtime was +21.09% and JPEG max
  displacement was +13.50%. The later tightened rebuild has no evaluator JSON.

Algobank evidence:

- `alg03_curble_hisruntri_rowedgpro` is the highest-confidence multicase
  pattern: current-blend target, history-runtime-trim congestion, overuse/disp/
  width ordering, row-edge probe, very-patient recovery, and no postopt. It was
  positive on AES, ibex, JPEG, and ariane, with small HPWL gains and generally
  lower runtime in the matrix.
- `alg39_softhr_oveonl_rowedgpro` is a strong JPEG quality/runtime pattern:
  JPEG HPWL was -14.32% and runtime -20.90% versus same-run baseline, but AES
  and ariane were weak/neutral. Treat it as a branch, not the default base.
- `bp_quad_nangate45` did not produce a passing algobank signal; the matrix
  timed out across the relevant patterns. Keep bp_quad as a separate stress
  gate, not a cheap promotion smoke.

## Decision

`netaware12_prefilter_hotset_guard` is the best current netaware artifact to
package because it repairs the R3/R1 runtime and JPEG max-displacement blocker
while preserving a legal HPWL improvement on AES/JPEG/ariane.

It is not a hard base yet because:

- Its quality is much weaker than the original `netaware11` signal.
- Runtime overhead is repaired but still about +18% to +20%.
- R5 suggests HPWL can be recovered, but the attempted recovery crossed runtime
  or displacement limits and has no clean tightened eval proof.

## Next Large Direction

Build `netaware14_rowedge_shortlist_hpwl` rather than continuing constant-only
tuning:

- Use algobank's `current_blend_history_runtime_trim_rowedge` as the cheap
  candidate frontier before any net traversal.
- Apply local HPWL delta only to R4-style eligible cells inside a small sorted
  shortlist.
- Keep fanout caps, per-cell net-eval caps, and the displacement outlier guard.
- Keep midpoint/connectivity-anchor probes fallback-only.
- Add explicit telemetry for shortlist size, net-eval count, skipped fanout,
  and displacement-guard rejects before widening the mechanism.

Do not restore full per-candidate net traversal and do not reintroduce active
anchor halos until the row-edge shortlist path passes the small/medium gates.

## Required Gates

1. Materialize `family_variants/netaware_objective` into a private source tree
   and build/relink a private OpenROAD binary.
2. Run strict same-run baseline comparisons on `aes_nangate45`,
   `jpeg_nangate45`, and `ariane133_nangate45`.
3. Reject if AES/JPEG/ariane runtime exceeds about +20% or if JPEG max
   displacement grows materially versus same-run baseline.
4. If those pass, run `bp_quad_nangate45` as a two-stage stress gate: legalizer
   return first, then full metrics completion with a longer timeout.

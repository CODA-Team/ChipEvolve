# DPO Cross-Legalizer Donor Matrix

## Evidence Type

- `measured_observation`: source-level cross-ablation on feature-diverse dense
  placement inputs. Metrics were collected from canonical OpenROAD DPL
  pin-based stage logs, not bbox proxy.
- `reference_donor`: the patches under `patches/evolved_dpo/` are donor
  patches for private `dpl_evolve` source trees. They are not universal
  defaults and must be evaluated on the active case.
- `working_hypothesis`: the best next improvement is to keep the NEG014 hybrid
  mechanism while making fallback descent more incremental or more selective.

## What Was Crossed

Legalizer seeds:

- `legalm`: evolved LEGALM/global-differential legalization line.
- `negotiation`: evolved NBLG/negotiation legalization line.
- `diamond`: evolved Diamond/local-greedy legalization line.

DPO/improve-placement donors:

- `base`: no improve-placement donor transplant.
- `diamond40_random`: a tiny touched-adjacent random cleanup from the Diamond
  DPO line.
- `neg014_hybrid`: Algorithm-1 kick selection plus Algorithm-2 local DP repair
  plus Algorithm-3 transaction/fallback descent from the negotiation DPO line.
- `legalm46_improve_only`: LEGALM DPO kernels, excluding LEGALM46's legalization
  handoff changes, so only the improve-placement side was transplanted.

The three evolved legalizer seeds had identical `src/Optdp.cpp` before DPO
transplant, so these donor results measure improve-placement transfer rather
than accidental legalizer-specific source differences.

## Cross-Matrix Result Pattern

Donor summary versus the same-legalizer base:

| DPO donor | transfer behavior | interpretation |
|---|---|---|
| `neg014_hybrid` | consistently quality-positive | strongest quality donor, but runtime-sensitive |
| `legalm46_improve_only` | quality-positive but weaker | rich mechanism donor, too broad as a default |
| `diamond40_random` | near no-op on transfer | safe micro-donor, not a final-HPWL strategy |

Best pairings observed:

| case archetype | best pairing | result signal |
|---|---|---|
| medium dense standard-cell | `diamond + neg014_hybrid` | local-greedy legalizer plus strong DPO can be best |
| high-damage dense image-style | `diamond + neg014_hybrid` | local-greedy legalizer plus strong DPO can beat global starts |
| large row-rich wrapper-style | `legalm + neg014_hybrid` | global legalizer plus strong DPO can recover more final HPWL |

Interpretation:

- The improve-placement donor matters as much as, and sometimes more than, the
  legalizer seed once the placement is legal.
- `neg014_hybrid` is the current best transferable DPO donor. It should be the
  first donor studied when final HPWL is limited by poor post-legalize recovery.
- `legalm46_improve_only` proves richer DPO kernels can transfer, but its broad
  kernel chain makes runtime a real design risk.
- `diamond40_random` is useful as an example of a safe micro-donor, not as a
  meaningful final-HPWL strategy.

## Runtime Mechanism Evidence

The major runtime sources were visible in DPL logs.

### `neg014_hybrid`

Mechanism:

- Algorithm 1: median incident-net optimal-region kick/partner selection.
- Algorithm 2: local DP repair around kicked rows.
- Algorithm 3: LSMC-style transaction accept/rollback with fallback descent.

Runtime source:

- Each LSMC transaction can call fallback descent.
- The fallback runs a detailed-placement script (`gs/vs/ro`, sometimes reverse
  reorder) and dominates runtime on dense cases.
- On the cross run, it remained the strongest HPWL donor despite this cost.

Policy:

- Do not delete this mechanism just because it is slower. Optimize the fallback
  controller or kernels first.
- A useful runtime repair should report fallback calls, skipped fallback,
  cheap/full fallback calls, gain, and runtime.

### `legalm46_improve_only`

Mechanism:

- Multiple DPO kernels are chained after the default improve pass: Algorithm-1
  batch swap, optimal-region refinement, vertical neighbor swap, window
  matching, window LSMC, single-row DP reorder, and region-guided multirow DP.

Runtime source:

- The Algorithm-2 DP kernels can create very large state spaces.
- On large row-rich inputs, logs showed very large DP transition counts in the
  broad kernels.
- Some LSMC refresh work was still single-threaded.

Policy:

- Treat this line as a rich mechanism donor, not the default deployable patch.
- If borrowing from it, select one bounded kernel and add ROI gates; do not
  append the whole kernel chain blindly.

### `diamond40_random`

Mechanism:

- Extends touched-adjacent random cleanup from one-hop neighbors to two-hop
  neighbors.

Runtime source:

- Very small. It does not add a global search, DP kernel, or transaction loop.

Policy:

- Safe to read as a minimal local cleanup idea.
- Do not expect meaningful transfer improvement from this patch alone.

## Runtime-Balanced NEG015 Variant

After the cross run, the negotiation DPO line produced
`neg015_staged_runtime`:

- patch: `patches/evolved_dpo/src_dpo_neg015_staged_runtime.patch`
- 014-to-015 delta: `patches/evolved_dpo/src_dpo_neg014_to_neg015_runtime_delta.patch`

Mechanism change:

- Keeps Algorithm 1/2/3.
- Replaces always-full fallback descent with staged fallback:
  `cheap gs/vs -> forward reorder if needed -> reverse reorder only if still needed`.
- Adds fallback telemetry: triggered/skipped, cheap/full/reverse calls,
  per-stage gain/runtime, DP windows/transitions, and transaction gain.

Feature-level result versus `neg014_hybrid` in the negotiation line:

| case archetype | 015 vs 014 quality | 015 vs 014 runtime | interpretation |
|---|---|---|---|
| medium dense | can improve | faster | promote if strict full flow agrees |
| high-damage dense | can regress | much faster | quality guard is required |
| large row-rich | can regress mildly | faster | use as runtime donor, then repair quality |

Policy:

- Use `neg014_hybrid` when maximum final HPWL quality is the goal.
- Use `neg015_staged_runtime` when runtime is a primary constraint or as the
  starting point for a 016 repair.
- A good 016 direction is to keep staged fallback but add high-ROI forward
  reorder fallback for cases where cheap `gs/vs` alone gives up too much HPWL.

## How Future Agents Should Use This

When a new case arrives:

1. Read stage-wise metrics first: `HPWLg`, `HPWLlg`, `HPWLimprove`, `HPWLfinal`,
   runtime, avg/max displacement, legality.
2. If legalization HPWL is bad but improve placement recovers a lot, work on
   legalizer handoff and post-legalize source selection.
3. If legalization is acceptable but `HPWLimprove -> HPWLfinal` remains weak,
   try `neg014_hybrid` as the first DPO donor.
4. If `neg014_hybrid` wins but runtime is too high, test
   `neg015_staged_runtime` or evolve a case-specific staged fallback from it.
5. If runtime explodes in DP kernels, inspect DP transition counts and exact
   scored candidates before increasing budgets.
6. If a local cleanup patch changes only a few random/reorder lines and metrics
   barely move, record it as a micro-donor and keep searching for a new HPWL
   source mechanism.

## What To Report Back To Teacher

A DPO Student should report:

- exact start seed and DPO patch/donor used,
- stage-wise HPWL and runtime table,
- fallback/descent/kernel telemetry from DPL logs,
- quality delta versus base and best known donor,
- whether the gain came from Algorithm 1 kicks, Algorithm 2 DP, fallback
  descent, detailed-orientation kernels, evaluation-mirror effects, or
  legalizer handoff. Evaluation-mirror effects are diagnosis only; they do not
  reopen downstream optimize-mirroring as an active patch target.

Do not claim a paper mechanism succeeded unless logs show it was active and the
canonical final strict metrics improved.

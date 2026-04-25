# Routing

Routing turns existing project knowledge into a bounded patch target.

- `patch_family_router.py` chooses the startpoint/family from design profile
  and effective-family rules.
- `region_selector.py` maps that family to one function-level patch surface
  from `adapters/science_codeevolve/patch_surface.yaml`.

Codex should not redo this routing during a bounded patch turn. It should follow
the selected family, target file, symbol, and line window in the current packet.

## Router Contract

The router should make the family choice before Codex patches code. The packet
given to Codex should already name the case regime, selected family, source
symbol, allowed line window, and the first-run evidence that motivated the
choice. Codex should not broaden scope after receiving that packet.

All families must use the same strict evolve command path. A family may change
the private `dpl_evolve` implementation that sits behind the command, but it
must not introduce a separate evaluator command, scoring rule, or flow path.

## Scale-First Routing Rule

Route base-family work toward scale-safe algorithms first.  Small cases such as
`aes` are smoke tests and calibration probes, not the optimization target that
defines a robust family.  A family promoted from routing must have an algorithmic
large-case story: row or spatial buckets, bounded active sets, dirty-region
checks, hotset refinement, capped repair queues, or similar complexity controls.
Small-case aggressive priority probes may remain in exploration, but they must
not outrank a large-case complexity fix when `jpeg`, `ariane133`, or `bp_quad`
show runtime stress.

Do not route a family into `robust_base` because it falls back to diamond,
default DPL, or another non-evolved implementation on large cases.  Such
fallbacks may be useful diagnostic fuses, but they are not family scalability.
If a variant only improves small designs and does not scale to `jpeg`,
`ariane133`, or `bp_quad`, keep it in exploration or small-case calibration.

## Robustness Status

The router distinguishes robust starting families from exploration families.
This keeps later agents from starting on a family that is known to be legal or
runtime fragile.

| Family bucket | Current status | Routing rule |
| --- | --- | --- |
| `search_narrow_runtime` | robust calibration/base probe | Safe first probe when no failure signature is known |
| `netaware_objective` | robust only for selected light variants | Use `netaware02` as safe base; use `netaware03` as quality-biased opt-in |
| `priority_escape` | repair target until guards are proven | Start from `priority_escape_scale_safe_base` or `priority_scale_safe_base`; keep old aggressive probes opt-in until runtime/HPWL guards exist |
| `localized_swap` | follow-up polish only | Use only after a legal/runtime-safe parent exists and postopt caps are proven |
| `legalm_engine` | important structural direction, currently opt-in | Do not route by default until the current `DPL-1803` legality failure is fixed; keep `legalm_base` and `legalm10` opt-in until Stage1/Stage2/Stage3 gates pass |
| `runtime_safe_fallback` | diagnostic safety fuse only | Keep out of robust-base scoring; use only to prove plumbing or collect failure evidence |

Current evidence says unguarded `priority_escape`, `localized_swap`, and
`legalm_engine` should not be default initial parents. They may produce useful
ideas, but they must pass aes/jpeg/bp_quad robustness gates before being
promoted into the default base set. For `bp_quad`, diagnostic evidence shows
the default diamond path can finish on the same snapshot while the negotiation
path times out, so the repair target is the negotiation/evolve algorithm, not
the ORFS snapshot. Full strict metrics for `bp_quad` are expensive; use a
`900s` gate unless that metrics stage is optimized separately.

## Case-To-Family Guide

| Case signal | Preferred family | Reason |
| --- | --- | --- |
| Small clean design, no failure signature yet | `search_narrow_runtime` | Cheap first probe that limits runtime risk while collecting evidence |
| Legal result but HPWL/timing proxy is weak | `netaware_objective` | Adds graph or local-wire information to candidate ranking |
| Repeated fallback, no-valid-candidate behavior, or late convergence | `priority_escape` | Changes main-pass search, active-set policy, and recovery behavior |
| Legal result with remaining local HPWL/displacement polish | `localized_swap` as explicit follow-up | Uses guarded post-legalization refinement only after correctness and runtime are known |
| Need structurally different initializer or repair path | `legalm_engine` as explicit structural comparison | Uses a materialized family implementation behind the same evolve command |
| Very large stress case such as `bp_quad` | scale-safe search/escape family with runtime pruning | Avoids applying small-case polish before runtime and search failure are understood |

For `aes` and other small cases, do not overfit with a heavy family before a
cheap strict probe. For `ibex` and `jpeg`, prefer net-aware objective families
unless the first run shows search failure. For `ariane133` and `bp_quad`, treat
runtime and no-valid-candidate evidence as first-class signals before trying
postopt-style polish; the first priority-family response should be bounded
frontier/dirty-region/candidate-cap work, not a wider small-case escape tune.

## First-Run Triage

The first strict run decides whether the next patch should be algorithmic or a
micro-tune.

| First-run result | Classification | Next patch depth |
| --- | --- | --- |
| Build, binary, or metric artifact failure | Infrastructure issue | Fix routing/build/evaluator plumbing, not algorithm constants |
| Illegal placement | Legalizer algorithm issue | Algorithmic change to recovery, rollback, active-set order, or candidate generation |
| Legal but runtime explodes | Search complexity issue | Algorithmic pruning, hotsets, caching, candidate caps, or component-local search |
| Legal and runtime stable, but HPWL/timing poor | Objective weakness | Algorithmic objective or candidate-ranking change |
| Legal and HPWL improves, but displacement regresses | Acceptance-guard weakness | Algorithmic guard or transactional rollback change |
| Legal and improved, with only small noise | Calibration case | One bounded micro-tune may follow the working mechanism |
| Multiple valid non-improving attempts from one family | Family mismatch | Switch family or symbol and record the failure signature |

Micro-tuning should be rare. It is appropriate only after a mechanism-level
change already produced a legal improvement and the remaining problem is a
small guard, normalization, or budget setting. If the first result does not
identify a working mechanism, the next patch should change algorithm behavior,
not only constants.

## Packet Expectations

A good routing packet should include:

- the case regime and first-run observation
- the selected family and why it fits that observation
- the selected source symbol and allowed line window
- one or two recent failure signatures to avoid
- the expected effect on HPWL, timing, runtime, displacement, and legality
- whether a micro-tune is permitted or an algorithm-level patch is required

This keeps Codex in the productive part of the search space: it can be bold
inside `dpl_evolve`, while the controller keeps evaluator, flow, and scoring
logic fixed.

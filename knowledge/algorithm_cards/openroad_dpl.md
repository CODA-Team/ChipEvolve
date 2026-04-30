# OpenROAD DPL — Human-Readable Card

## What Codex should remember

OpenROAD DPL currently exposes **two legalizer engines at runtime**:

1. **Diamond search** (default)
2. **NegotiationLegalizer** (`-use_negotiation`)

Within the negotiation engine, the public docs describe a logical flow:

- Abacus pass (optional / skippable)
- Negotiation pass
- Post-optimisation

At the flow level, ORFS `detail_place.tcl` is **not a pure legalizer stage**. It may include:

- `balance_row_usage`
- `set_placement_padding`
- `detailed_placement`
- `improve_placement`
- `optimize_mirroring`
- `check_placement`
- `estimate_parasitics -placement`

Therefore:
- Legalizer-stage claims should be labeled separately from full-flow claims.
- Current repo promotion decisions use the complete configured flow, including
  detailed placement, improve placement, and mirroring.
- HPWL promotion uses `metrics.json:hpwl`, parsed from OpenROAD/DPL pin-based
  log reports.  Local or bbox HPWL proxies are diagnostics only.

## High-value surfaces

### 1. `NegotiationLegalizer.cpp`
Useful place to evolve repair mechanisms:
- cost
- search window
- negotiation schedule
- disabled or incomplete postopt
- escape / refinement logic

### 2. `Opendp.cpp`
Useful place to evolve dispatch and framework wiring:
- engine dispatch policy
- top-level setup around detailed placement
- future initialization hooks

### 3. `Opendp.tcl`
Useful place to evolve only if a C++ knob genuinely needs a Tcl surface:
- expose a carefully chosen knob
- keep Tcl <-> C++ synchronization correct

## What not to confuse

- `detailed_placement` = legalizer core entry
- `improve_placement` = DPO / different optimization subsystem
- `optimize_mirroring` = HPWL polishing after legalizer

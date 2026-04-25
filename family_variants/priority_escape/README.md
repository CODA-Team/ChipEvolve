# priority_escape

This directory is intentionally a status/repair manifest, not a materialized
base variant.

Current decision: `priority_escape` is useful only as a repair line after real
stuck/no-valid telemetry exists.  The existing R3 patch is normal-case safe on
aes/jpeg because diamond returned with zero failures before escape ran, so it
does not prove priority escape behavior.

Use the manifest in `manifest.yaml` as the flow-facing state:

- Do not autoload `priority_escape` as a base family.
- Do not treat diamond-first fallback as promotion evidence.
- Add telemetry first, then run a real stuck/no-valid gate.
- Only after that should a patch be normalized into a standalone
  `dpl_evolve.patch`.

Committed research patches:

- `research_patches/priority_escape_r3_20260425.patch`
- `research_patches/priority_escape_frontier_repair_20260425.patch`

These patches expose the current repair code to research agents.  They are not
base-family patches and should not be enabled without the telemetry gates above.

Evidence:

- `../../family_robustness/priority_escape/HARDENING_DECISION_20260425.md`
- `../../family_robustness/priority_escape/WORKER_RESULT_R3_20260425.md`
- `../../knowledge/algorithm_cards/priority_localized_card.yaml`

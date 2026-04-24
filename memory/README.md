# Evidence Memory

This directory contains lightweight helpers for evidence-driven evolve loops.
Runtime data is written under `$DPL_EVOLVE_STATE_ROOT/memory`, not into this
repo.

Current stores:

- `run_db.jsonl`: one structured record per Codex/evaluator attempt.
- `observations.jsonl`: factual observations extracted from RunDB records.
- `knowledge_cards.jsonl`: compact prompt fragments with evidence and scope.
- `family_region_stats.json`: posterior counters for patch families and target
  symbols.

The packet builder reads recent RunDB failures before each Codex attempt so the
next prompt can avoid repeating rejected mechanisms. The learning step also
updates knowledge cards and family/region stats after each attempt.

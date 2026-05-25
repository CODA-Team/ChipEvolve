# Knowledge Base

This directory contains compact paper, algorithm, mechanism, and workflow notes
for the constrained `detailed_placement_evolve` framework.

## Route Contract

Knowledge cards are not all equal. Teacher route mapping for case-specific DPL
evolution must start from the current case evidence and the two core
case-evolution files:

1. `insights/case_evolution/case_type_quality_mechanism_priority.md`
2. `insights/case_evolution/mechanism_reconstruction_roadmap.md`

The generated `matched_blueprint_packet.md` is the normal entry point because it
filters those two files to the current case. Other insight files are inspiration,
mechanism support, evidence archives, or workflow contracts. They may refine a
selected blueprint or diagnose a failure, but they must not directly replace the
core route map.

## Default Reading Order

1. `../README.md`
2. `../AGENTS.md`
3. `EVIDENCE_POLICY.md`
4. `../baseline/canonical_lines.yaml`
5. `../family_variants/REFERENCE_INDEX.yaml`
6. `insights/README.md` for file roles and insight hygiene
7. generated `matched_blueprint_packet.md` in the current Teacher round packet
8. `insights/case_evolution/case_type_quality_mechanism_priority.md` only when
   the generated packet is insufficient
9. `insights/case_evolution/mechanism_reconstruction_roadmap.md` only for the
   selected blueprint section
10. `index/skill_cards.jsonl` through `../scripts/query_knowledge.py` only to
    sharpen a selected stage mechanism, liveness check, or failure diagnosis
11. one relevant `insights/dpo/`, `insights/legalization/`, `insights/legalm/`,
    `skills/`, or `algorithm_cards/` file after the route needs it
12. paper PDFs and source notes under `reference/` only if needed

## Insight Hygiene

- Do not put local experiment paths, run-state paths, old program ids, raw
  result-table filenames, or benchmark-specific result rows in default
  knowledge. Translate them into design features, source mechanisms, liveness
  signals, and failure modes.
- Keep case-type routing in the two core files above. If a support card repeats
  a route idea, collapse the mechanism into the core blueprint and leave the
  support card as background evidence.
- A mechanism is strong only when same-case final `metrics.json:hpwl` improves
  with clean legality and source/log liveness. `HPWLlg` is diagnostic, not a
  standalone objective.
- Legalization-side improvements must preserve avg/max displacement, a
  DPO-recoverable local order, useful handoff state, and downstream exact
  accepted gain.
- Prepared start branches (`framework`, `evolved_diamond`,
  `evolved_negotiation`, etc.) are source basins, not edit-scope restrictions or
  universal answers.

## Core Mechanism Families

The core roadmap merges repeated ideas into mechanism families instead of
letting many cards describe near-duplicates:

- Diamond/source-edge exact DPO with canonical replay/restore;
- large row-rich critical-frontier Diamond-DPO chain;
- negotiation hot-segment exact consumer stack;
- wrapper/macro row-window replay and handoff;
- top-net target/source repair with mirror only as downstream consumer;
- recoverable producer plus hot-segment exact consumer;
- adaptive transactional basin escape;
- negotiation-compatible residual transaction handoff;
- row-local or edge-local exact closure;
- conflict-primary legal closure with DPO consumer;
- plateau escape by changing producer, payload, move family, objective,
  transaction granularity, or preservation contract.

## Support Areas

- `insights/dpo/`: DPO consumer, basin, frontier, and handoff mechanism support.
- `insights/legalization/`: legalizer role, liveness, and flow support.
- `insights/legalm/`: LEGALM paper/code alignment and runtime/reference support.
- `insights/workflow/`: experiment, metric, and Teacher/Student workflow
  contracts.
- `algorithm_cards/`: pseudocode and background references used only when a
  selected route needs algorithm detail.
- `skills/`: concise stage skill notes discoverable through
  `scripts/query_knowledge.py`.

Use `EVIDENCE_POLICY.md` to distinguish hard contracts from measured
observations, working hypotheses, and reference donors. Current metrics, logs,
legality, source diffs, and final full-flow HPWL override any stale card.

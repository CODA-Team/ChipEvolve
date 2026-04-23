# CODEX TASK 01 — Bootstrap the minimum viable control plane

## Goal
Create the first minimal, repo-local control plane for `dpl_evolve` without contaminating the target plane.

## Scope
Work only in:
- `evolve_agent/`

Do **not** modify:
- `tools/OpenROAD/src/dpl_evolve/src/*`
unless the task explicitly enters algorithm evolution.

---

## Phase A — Verify repository assumptions

### A1. Confirm target plane layout
Verify that these exist locally:
- `tools/OpenROAD/src/dpl_evolve/src/`
- `tools/OpenROAD/src/dpl_evolve/include/`
- `tools/OpenROAD/src/dpl_evolve/test/`
- `evolve_agent/baseline/`
- `evolve_agent/knowledge/`

### A2. Confirm baseline harness layout
Verify that these exist locally:
- `evolve_agent/baseline/run_baseline.sh`
- `evolve_agent/baseline/run_baseline_suite.sh`
- `evolve_agent/baseline/run_evolve_line.sh`
- `evolve_agent/baseline/collect_metrics.py`
- `evolve_agent/baseline/report_legalized_metrics.tcl`

### A3. Confirm artifact plane layout
Verify that ORFS still writes to:
- `flow/results/...`
- `flow/reports/...`
- `flow/logs/...`
- `flow/objects/...`

### Deliverable
Write a short verification note:
- `evolve_agent/tasks/task01_repo_verification.md`

---

## Phase B — Install / wire control plane skeleton

### B1. Create the control-plane directories
Ensure these exist:
- `evolve_agent/skills/`
- `evolve_agent/configs/`
- `evolve_agent/problems/`
- `evolve_agent/knowledge/`
- `evolve_agent/adapters/science_codeevolve/`
- `evolve_agent/scripts/`
- `evolve_agent/checkpoints/operations/`

### B2. Keep external runtime references optional
If upstream control-plane tooling is consulted later, keep it outside the
target plane and behind `evolve_agent/adapters/`. Do **not** move it into
`tools/OpenROAD/`.

### B3. Copy / refresh AGENTS contract
Ensure `evolve_agent/AGENTS.md` exists and matches the current architecture.

### Deliverable
- a committed or staged control-plane skeleton
- no target-plane changes

---

## Phase C — Make evaluator wrapper minimally runnable

### C1. Implement `evaluator.py`
`evolve_agent/adapters/science_codeevolve/evaluator.py` must:
1. accept `--problem`, `--run_root`, `--out`
2. call the existing build pathway
3. call the existing baseline harness (do not reimplement it)
4. locate `metrics.json`
5. write a compact evaluator JSON

### C2. Add dry-run behavior
If build/run commands are not yet finalized, add a `--dry_run` mode that:
- prints the resolved commands
- validates paths
- exits successfully

### Acceptance criteria
- `python .../evaluator.py --help` works
- `python .../evaluator.py --dry_run ...` works
- no algorithm code is modified in this phase

---

## Phase D — Make KB packet generation runnable

### D1. Implement `kb_query.py`
It must:
- read `problem.yaml`
- read selected KB files
- emit:
  - `knowledge/packets/current_run_packet.json`
  - `knowledge/packets/current_run_packet.md`

### D2. Ensure packet is compact
The packet must be small enough for Codex to consume directly.
Do not dump full papers or whole repo summaries.

### Acceptance criteria
- packet generation completes for `gcd_nangate45`
- packet includes:
  - stage context
  - selected patch surface
  - relevant delta ledger
  - selected playbook
  - hard gates

---

## Phase E — First smoke execution

### E1. Generate packet
Use `kb_query.py` for `gcd_nangate45`.

### E2. Do not patch algorithm yet
This task is still bootstrap-only.

### E3. Run one baseline in dry-run or real mode
The goal is only to prove evaluator wiring.

### Deliverable
Create:
- `evolve_agent/tasks/task01_smoke_report.md`

The smoke report must contain:
- packet path
- baseline command used
- metrics path (or why unavailable)
- open issues blocking full loop

---

## Final acceptance criteria

Task 01 is complete only if:

1. Control plane exists as a separate tree
2. Any external runtime references remain outside the target plane and behind
   the local adapters
3. `evaluator.py` exists and runs in help/dry-run mode
4. `kb_query.py` generates packet files
5. No accidental control-plane code is placed under `tools/OpenROAD/src/dpl_evolve/`

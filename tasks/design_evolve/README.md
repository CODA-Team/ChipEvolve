# Design Evolve Prompts

These prompt files are the design-specific Codex entrypoints for the placement
cases listed in:

- `flow/run_place_batch.sh`

## Required prerequisite

Run the initial place batch first if the snapshots are not already present:

```bash
./evolve_agent/scripts/run_place_batch.sh
```

These prompts assume:

- the design already has a reusable `3_4_place_resized.odb`
- Codex should start directly from code evolve, not from rerunning place

## How to use

Run one prompt through the local Codex wrapper:

```bash
python3 evolve_agent/scripts/run_codex_exec.py \
  --operation-id codex_ibex_n45 \
  --prompt-file evolve_agent/tasks/design_evolve/nangate45__ibex.md \
  --sandbox workspace-write
```

Each prompt points Codex at a matching local problem definition under
`evolve_agent/problems/`, so `kb_query.py` can refresh the packet for that
design before patching.

If you want the control plane to keep iterating automatically and preserve
cross-attempt memory, use the Python loop entrypoint instead:

```bash
python3 evolve_agent/scripts/run_design_evolve_loop.py \
  --problem evolve_agent/problems/gcd_nangate45/problem.yaml \
  --max-attempts 3
```

That loop writes a local experience journal for the design evolve session and
feeds a compact memory excerpt back into the next Codex attempt.

## Available prompts

- `nangate45__ibex.md`
- `nangate45__jpeg.md`
- `nangate45__aes.md`
- `nangate45__ariane133.md`
- `nangate45__bp_quad.md`
- `asap7__aes.md`
- `asap7__ethmac.md`
- `asap7__gcd.md`
- `asap7__ibex.md`
- `asap7__jpeg.md`
- `asap7__megaboom.md`
- `asap7__riscv32i.md`
- `asap7__swerv_wrapper.md`

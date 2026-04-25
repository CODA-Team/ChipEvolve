# Problems

Each subdirectory defines one design/platform evolve problem.

A problem is the canonical control-plane handle for a case. It should answer:

- which design
- which platform
- which evaluation mode
- which baseline or objective framing we care about

## Convention

- one directory per case
- one `problem.yaml` per directory

Examples:

- `gcd_nangate45/problem.yaml`
- `aes_asap7/problem.yaml`
- `ibex_nangate45/problem.yaml`

## Notes

- Design-specific prompt files live under `../tasks/design_evolve/`
- Design-specific regime hints live under `../knowledge/design_profiles/`
- Baseline outputs still live under the ORFS `flow/` tree

## Case Sets

`case_sets.json` contains only named lists of case ids, such as `default`,
`smoke`, `large_gate`, and `place_batch`. It is not a second source of case
facts. Scripts must resolve every case id back through this directory's
`problem.yaml` files.

# Family Components

This folder stores reusable algorithm components, not whole experiment runs.

Use these files when a family is no longer just a one-off patch and has become
something we may want to:

- reuse on another case
- stack with another family
- promote into a more permanent patch recipe

Each component should answer:

- what mechanism it changes
- where it lives in code
- what metrics it usually helps
- what metrics it can hurt
- which other components it stacks well with
- whether it lives in the clean main-tree base or in a materialized family variant

This folder defines reusable families, not baseline lines. Read the baseline
line list here first:

- `../../baseline/canonical_lines.yaml`

The canonical family-level status still lives in:

- `../replay_bank/family_registry.yaml`

For the shortest effective-only entry point, read:

- `effective_families.yaml`

For the first choice after a new baseline run, read:

- `initial_patch_paths.yaml`

For the shortest current answer to "what should I start from now?", read:

- `effective_families.yaml`

This folder is for reusable building blocks.

If a family needs its own source tree, the component should point at the
matching manifest under:

- `../../family_variants/`

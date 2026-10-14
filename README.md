# EDA Toolkits

OpenROAD/ORFS tool commands and native result normalization live here. Execution
Foundation manages their lifecycle through its existing plugin contract.
Data Foundation stores and relates the exported facts and source identities.

Install a wheel into a dedicated environment, then materialize plugin manifests
in a runtime directory using `eda-toolkit configure --output DIR`. The manifest
uses that environment's Python and the installed module. It contains no copied
adapter code or dependency on a sibling checkout. Point Execution Foundation's
`--plugins-root` at that directory; admission remains an EF-owned decision.

`eda-toolkit doctor --config CONFIG` checks explicit tool configuration. Running
an analysis requires an explicit submission; reading data never runs a tool.
Tool binaries, ORFS checkout and licensed technology libraries are deployment
inputs, and are not bundled in the wheel.

## Frozen shared objectives

`eda_toolkits.objectives` is a small public helper for platform consumers.
`load_objective(path)` checks the frozen JSON identity; `verify_conditions(goal,
sdc=...)` checks the actual Liberty and SDC contents. `append_objective(prompt)`
and `objective_messages(payload)` expose `EDA_PLATFORM_OBJECTIVE` to the actual
professional model request. `bind_task_objective(spec, path=None)` stages the
same goal through existing TaskSpec fields, without a new service or API.
`condition_id(goal)` identifies comparison conditions by contents rather than
machine paths; `require_same_conditions(left, right)` rejects mixed-condition
measurement comparisons. None of these functions score or promote candidates.

The `chip-evolve.objective.v1` document contains `design_id`, `reference_run_id`,
`conditions` (toolchain, actual libraries and SDC with SHA-256, corner, clock,
propagation, parasitics and units), `constraints` (timing, legality, power and
separate cell/core/die area limits), and a canonical `objective_id`. Goals are
explicit opt-ins; professional native evaluation and final measurement are
labelled separately. Runtime goal files belong outside source repositories.

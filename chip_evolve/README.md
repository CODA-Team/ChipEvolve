# Root business orchestration

Read these three files first:

1. [workflow/cli.py](workflow/cli.py): CLI arguments become typed requests.
2. [workflow/commands.py](workflow/commands.py): preflight, experiment transaction and command outputs.
3. [workflow/professional.py](workflow/professional.py): specialist input inspection, fact preparation and dispatch.

| Package | Owns |
|---|---|
| `core/` (19 modules) | Contracts, validation/selection rules, deployment, toolchain profile, named resource budgets and shared execution primitives. |
| `facts/` (6) | Design facts, evidence, recipes and frozen source preparation. |
| `execution/` (5) | Physical execution, output proof and deterministic checkpoint delivery. |
| `workflow/` (21) | The three entry points above, professional adapters, diagnosis/handoff, comparison/validation and replay/recovery. |

Dependencies go to the same or a lower package and obey the original five
logical layers without cycles. `core/` includes execution primitives; it is
not a pure value-object package. Goal and ECO have separate owners. `native`
only re-exports its six original objects. The four specialist adapters retain
the same six typed arguments while preserving native algorithm differences.

Start with `core/contracts.py` for Result, Handoff and SpecialistRequest/Reply.
`result_io.py` and `handoff_io.py` validate existing wire formats and preserve
raw-file hashes. Invalid data is rejected; finite constraint failures remain
research evidence. Specialist promotion, independent validation and platform
adoption are distinct decisions.

`core/toolchain.py` consumes the versioned integration layout compatible with
the pinned Toolkits family. `core/resources.py` resolves explicit task budgets
and checks total EF capacity before new submission/upload or native dispatch.
EF still owns scheduling. Completed recovery keeps its original identity and
saved resources. The fixed `_compat.py` table and two minimal root runners
preserve 49 legacy module identities; new code imports canonical owners.

`delivery` verifies all candidate evidence before further EDA and rejects
corrupt completed references. Flow terminal delivery owns a separate lock;
lock order remains business lock then flow-delivery lock. A failed native
search remains `evidence_only`, even if measured branches can be delivered.

`resume` reuses saved tasks and continues deterministic delivery. Exit 3 means
pending, not completed or cancelled. `validate` independently proves outputs,
replays physical work and checks SDK facts. `select` records the caller's
adoption decision only with matching validation and constraints. No historical
result is rewritten to repair recovery.

See [Architecture](../ARCHITECTURE.md) for the full chain and
[Task status](../TASKS.md) for the actual verification scope. Complete real Code
additional delivery, Flow collector and some Goal historical recovery evidence
remain inherited gaps; directory moves and GCD checks do not close them.
TUI/Web remain frozen pending owner acceptance of the backend prerequisites.

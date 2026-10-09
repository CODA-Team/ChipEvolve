---
name: task-handoff
version: 1.2.0
---

Deliver a task package with the objective, fixed input identities, confirmed
facts, unconfirmed hypotheses, source evidence, allowed actions, budget, success
conditions and refusal conditions. Do not describe an untested ECO as a fix.
Use action=handoff with a scoped handoff request and an evidence-backed answer.
The application builds and persists the actual package from retrieved inputs.
Buffer permissions come from the operator's configuration for that snapshot;
you cannot add cells or allowed masters. Preparation is not receiver acceptance.
If the request needs permissions that were not granted, report that exact gap.

The first receiver is a Codex ECO consumer. It may resize only explicitly
allowed buffer cells. Clock/constraints/libraries/corner/RC and evaluation
conditions remain fixed. Require the patch, new experiment ID, original STA,
area and setup/hold checks. Reject an out-of-scope edit or changed evaluation
conditions. Query Agent rechecks improvement and side effects independently.
No improvement is a valid measured outcome. Flow and Code roles have contracts
only until their real consumers are connected and measured.

Respect measurement precision: a rounded area report with equal integer values
does not prove unchanged area. State its resolution and request or use a precise
measurement when that affects the acceptance decision. Counts do not prove equal
area. State the area basis (library area, placed cell geometry, and whether
physical-only cells are included). "Acceptable" requires the package's declared
criterion. Positive slack in a stored sample does not certify all-path closure.

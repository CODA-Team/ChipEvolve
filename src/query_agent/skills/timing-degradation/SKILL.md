---
name: timing-degradation
version: 1.5.1
---

Investigate timing degradation through competing explanations and discriminating
observations. First fix the baseline/candidate snapshots, setup vs hold, corner,
units and constraints. Never compare numbers with different analysis conditions
without explaining that difference. Worst slack and worst negative slack (WNS)
are different: WNS = min(0, worst slack) over the stated path domain. A positive
hold slack is a worst-slack observation, never a positive WNS. A worst endpoint
switch does not establish that the previous worst path became slower. Setup can
improve while remaining negative. Compare the previously worst endpoint in both
scopes before deciding whether the change improved setup. A larger reported area
number has a larger direction; rounding limits its precision, not its sign.

Read compact summaries and constraint context in one batch. Request explicit
slack_ns,arrival_ns,required_ns alongside path_id,startpoint,endpoint. Original
slack/arrival fields in SI reports are seconds; never label those values ns.
Preserve each scope's initially sorted worst endpoint as a fixed observation:
a later same-endpoint lookup is a different selection, not its new worst path. Compare arrival and
required time separately, then query the same endpoints in both experiments.
Account for input/output delays, clock period/uncertainty/latency, RC mode,
propagation, cell masters, loads, slew and individual cell/wire increments.
Do not convert a changed constraint into a claimed physical regression.

An unchanged worst path does not establish unchanged timing throughout the
stored sample. If physical inputs changed, locate the affected instances:
read compare/{other_snapshot}/inventory with include_instance_changes=1.
For each relevant changed master, read its instance engineering to obtain its
object_id, then timing-points filtered by instance_id with fields=path_id,pin_name,
cell_name,arrival_ns,load_ff,slew_ns. Query those paths' same endpoints in both
snapshots, including setup and hold; read the native area report for sizing side
effects and state its rounding precision. Inspect original fragments for numerical
increments and precision. Do not substitute unrelated worst paths for this check.
Resolve instance IDs independently in each snapshot. An empty candidate filter
cannot prove absence in the baseline or across unsampled paths. If the affected
endpoint is absent, request directed STA with the fixed inputs.

Read preview-truncated evidence before calling it missing. When imported
supplemental analysis succeeded, inspect its data before delivering a conclusion.
Use remaining budget for the next discriminating observation that you can perform;
defer it only when the actual input, permission, time or call limit prevents it.

Maintain hypotheses with support, counterevidence and the next observation that
would distinguish them. Test alternatives before concluding. A measured cell
delay or RC correlation alone is insufficient for an exclusive cause. State a
supported mechanism and unresolved alternatives when uniqueness is not proven.

Stored timing paths are samples. Empty filters can mean an unsampled path, not
no path. If the explanation needs a missing endpoint report, explicitly request
STA with the original ODB, libraries, SDC and RC inputs, named endpoints and a
verification question. Do not request an identical analysis twice. Both setup
and hold are exported; specify which check supports each claim. Wait or pause
for the result, import its new identity and continue on that identity.

Before delivery check every numeric claim against its cited selection and units.
An endpoint-filtered hold lookup is that endpoint's hold slack, never the global
worst hold slack. A later matched-endpoint lookup does not replace the initially
sorted worst setup result. Avoid extra numeric claims not needed for the task.

Finish with scoped observations, cited support, rejected alternatives, remaining
gaps and a concrete next action. Unknown input/corner/scope must remain unknown.
Read original source excerpts for key causal evidence before final delivery.

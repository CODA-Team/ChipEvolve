---
name: experiment-comparison
version: 1.0.0
---

Pin both experiments and their design/stage/corner/check/units. Retrieve their
summaries and needed facts in a single batch, then expand only discriminating
objects or paths. Compare the same endpoint and complete count domain whenever
possible. Keep global WNS, endpoint slack, net fanout and timing sample size
separate. Report delta = candidate minus baseline, naming units and sign.

Use source IDs and SHA256, including the native report location of each value.
Pagination does not imply completeness: retain count/next_offset/coverage and
request further pages when the answer depends on the whole collection. An
object name may repeat across snapshots; never transfer its identity without
resolving it in the second scope. Missing data is a gap, never zero.

Do not infer causation from an inventory/metric delta. Identify changes in
constraints, libraries and parasitic conditions before comparing physical
performance. Preserve contradictory observations. Answer simple fact and fixed
comparison questions promptly once their required evidence is sufficient.

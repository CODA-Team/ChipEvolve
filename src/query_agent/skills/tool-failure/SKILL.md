---
name: tool-failure
version: 1.0.0
---

Use the recorded job status, terminal reason, failure details, original tool log
and input hashes. Separate tool configuration, input/load errors, real tool
failure, timeout, cancellation and missing report. Tool exit success without
the promised artifact is an export failure. A failed analysis produces no new
timing fact. Do not substitute an earlier experiment's successful report.

Propose a targeted correction tied to the observed failure and preserve the
first attempt. Respect analysis/time budgets. If retries cannot advance the
question, stop with the exact missing evidence, why it matters and a possible
next experiment. Never repeatedly submit the same failing task without changed
inputs or a documented transient reason.

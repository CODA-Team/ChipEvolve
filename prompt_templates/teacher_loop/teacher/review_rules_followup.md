# Teacher Review Follow-Up Rules

Use prior Teacher memory; review only current artifacts needed for the next
route. Keep the review concise and action-bearing.

- Validity gate: build/evaluator/metrics/diff/message/legality/artifact source
  must be clean before a candidate can be promoted.
- Rank by legal final `metrics.json:hpwl`; use `G_HR` only to explain runtime
  value or runtime-repair priority.
- Runtime below the hard budget is available search headroom. If a candidate is
  legal but HPWL-poor and baseline-fast, classify the issue as possible
  under-exploration and route stronger bounded search instead of rewarding speed.
- Identify the real mechanism and whether counters/logs prove it executed. Zero
  counters or stale source/binary/metrics means non-executed/negative evidence.
- Treat `reject` as not-final-for-this-trial, not automatic method death. Use
  source diff, counters, logs, and stage movement to decide implementation bug,
  handoff/composition issue, method-low-ROI, or hard non-promotable failure.
- Classify each useful result as `final donor`, `stage donor`, `active
  mechanism workbench`, `validated-low-ROI`, `non-executed route`, or `negative
  evidence`.
- If a verified mechanism gives extremely small full-flow HPWL movement after
  a meaningful repair attempt, mark `validated-low-ROI` and stop assigning
  repeated tie-break/threshold/local-polish variants as primary routes.
- Preserve stage donors when downstream erases a gain; route the next Student to
  handoff/consumer repair rather than discarding the stage mechanism.
- If a Student restored a better final source, use `source_trials.jsonl` refs as
  evidence for any useful rejected or kept workbench. If repairable, tell the
  next Student to use `25_trial_source.sh begin --from-ref <ref>`.
- Next packets must be non-accumulative: one distinct HPWL-source hypothesis,
  concise A/B/C plan, exact function/state handles, runtime tier, liveness
  counters, and the low-ROI stop condition when relevant. A/B/C may include
  preservation or diagnosis; do not require cosmetic edits.

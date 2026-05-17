## Output Format

Write a compact review only:

- validity gate: build/evaluator/metrics/source/diff/legality status
- result table: final HPWL/runtime/legality plus `G_HR`, HPWL_gain%, runtime_penalty_pp
- stage attribution: where legalization, DPO, or handoff helped or erased gains
- mechanism classification: final donor, stage donor, workbench, validated-low-ROI, non-executed, or negative evidence
- mechanism reasoning check: whether the Student explained source changes, liveness evidence, and repair/pivot thinking
- knowledge synthesis: which knowledge/algorithm idea supports or rejects the next route
- efficiency diagnosis: useful controlled runtime cost, over-cost, or under-exploration
- next routing decision: preserve, repair, pivot, or freeze

End with:

```text
## Next Insight Packets
$student_insight_packet_format
```

Use exact student IDs from the artifact packet only.

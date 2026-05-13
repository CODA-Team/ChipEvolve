## Output Format

- compact result table
- `G_HR`/HPWL_gain%/runtime_penalty_pp value check next to raw HPWL/runtime
- stage-wise attribution table
- runtime-tier attribution table
- best lineages
- final donors, stage donors, active mechanism workbenches, non-executed routes,
  and negative evidence
- efficiency bottlenecks
- under-exploration or over-spend diagnosis
- mechanism knowledge used or missing: selected skill ids, algorithm/pseudocode
  cards, and whether the Student proved the expected counters
- workbench repair routes to continue
- matrix candidates to freeze, if any
- knowledge cards to preserve

End with:

```text
## Next Insight Packets
$student_insight_packet_format
```

Use exact student IDs from the artifact packet only.

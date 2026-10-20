# GCD case study: text and table for the invited paper

Evidence checkpoint: 20 October 2026. This section describes completed GCD measurements and validations; the original three-Student DPL round is still finishing. The table is a set of actual branches. Each parent column specifies the physical design state used by the next professional.

## English draft

**A measured optimization relay.** We use GCD to demonstrate how Codex combines professional physical-design capabilities through a shared execution and design-fact environment. Flow searches design configurations and saves intermediate physical checkpoints. DPL and Goal retain their native source-optimization procedures, while ECO retains its native timing-repair session. Codex chooses the next task from the measured design state; the platform executes it, records the artifacts, and exposes the resulting facts for the next decision.

The retained branch starts from the completed Flow candidate F37. Under the final ASAP7 FF, 310 ps condition, this candidate has 0.890912 mW power and 44.8918 µm² cell area, exceeding the original 42.6757 µm² area bound. Query supplies the design facts and diagnostic context to Goal. The completed Goal round produces G02 at 0.715649 mW and 39.1181 µm²: power decreases by 19.67% and cell area by 12.86% relative to the actual Flow parent. Setup and hold timing close, electrical and placement violations are zero, and the native detailed-route count is zero. All 18 digital outputs pass sequential equivalence, and an independent complete routing/extraction replay reproduces the seven recorded PPA values exactly.

**Continuing from a locally useful intermediate state.** A second branch consumes the saved F37 placement checkpoint with DPL. Its completed Student01 reduces native HPWL from the Diamond reference of 536.9 µm to 530.9 µm. Common final measurement, however, yields 0.937516 mW and 44.9793 µm², so this intermediate result is not adopted. Query records the discrepancy between the local wirelength objective and final PPA, and Codex hands the actual DPL state to Goal. The resulting DG1 branch reaches 0.819291 mW and 39.6139 µm², reducing power by 12.61% and area by 11.93% relative to its DPL parent while closing final timing. DG1 passes all-output equivalence and an exact independent routing/extraction replay. Codex archives this legal relay and keeps G02 as the lower-power incumbent. The two Goal branches use different native stage/strategy settings; the comparison is a record of actual optimization paths, rather than an isolated estimate of DPL's causal contribution.

**A genuine ECO attempt and the acceptance decision.** The timing-failing Goal candidate G03 supplies another branch with real work for ECO. Its initial setup TNS is −0.856145 ns. The original eight-round ECO session reduces the magnitude of this violation by 69.07%, to −0.264783 ns. Native routing still has 54 violations. A separately recorded routing-completion operation brings the native route count to zero, but setup TNS remains −0.266838 ns. Codex therefore rejects the branch and retains the valid incumbent. This sequence demonstrates actual specialist participation, evidence-based continuation, and rejection of an unsuccessful final outcome. It is reported as a branch, not as a successful serial traversal of all four professionals.

**What the platform contributes.** Every new tool experiment in these branches is submitted through EF, including professional tool calls, common physical measurement, and validation. EF supplies task identity, resource admission, logs, and registered artifacts. DF imports the outputs and provides scoped facts through DI; Query preserves observations, hypotheses, evidence references, and professional handoff context. The DPL-to-Goal handoff retains the design cells, connectivity, constraints, and source identities, while Goal explicitly rebuilds signal routing in its own source workspace. Codex makes the optimization and acceptance decisions without directly managing tool processes or service databases. The recorded operation trace demonstrates this separation; no unmeasured token or wall-clock saving is inferred.

## Completed final measurements

All rows below use the same final GCD condition. Cell area is distinct from core/die area, which remain available in the full CSV. WS denotes measured worst slack; canonical WNS is min(0, WS). The native route count is the count reported by the original detailed-routing method.

|Node|Actual design-state parent|Professional / operation|Power (mW)|Cell area (µm²)|Setup WS (ps)|Setup TNS (ns)|Native route count|Outcome|
|---|---|---|---:|---:|---:|---:|---:|---|
|F37|saved Flow search state|Flow|0.890911557|44.8918|12.289000|0|0|area rejected; retained as exploration input|
|G02|F37|Goal|0.715648639|39.1181|0.083406|0|0|validated incumbent|
|D01|F37 saved placement|DPL + common completion|0.937515520|44.9793|10.494300|0|0|area rejected; Goal continued this state|
|DG1|D01|Goal|0.819291221|39.6139|1.315860|0|0|validated legal relay; G02 retained|
|G03|F37|Goal|0.768538506|38.7974|-70.480200|-0.856145|0|setup rejected; actual ECO input|
|GE8|G03|ECO, eight native rounds|0.770871644|38.9432|-32.433100|-0.264783|54|setup and route rejected|
|GEC|GE8|separate routing completion|0.770615239|38.9432|-32.493400|-0.266838|0|setup rejected|

The complete CSV also reports hold WS/TNS, core/die area, slew/capacitance/fanout and placement violations, condition/objective IDs, run IDs, and original-result hashes. The ORFS B0 reference has a different synthesis/method lineage; the end-to-end difference from it is separate from the within-branch improvements above. Independent checker markers are retained separately and do not support a signoff-clean claim.

## 中文要点（供审稿沟通）

本案例最直接的结果是：Flow给出一个低功耗但面积超限的设计，Goal继续优化后既降低功耗，又修复面积，形成合法结果。新增的Flow→DPL→Goal分支也完成了同样可追踪的真实接力；DPL的局部线长收益没有直接变成最终PPA收益，后续Goal把中间态修复成合法方案。ECO确实尝试修复另一个有时序问题的分支，但最终没有达标，因此平台保留更好的既有结果。

平台的价值体现在两处：一是专业能力能够接力处理同一设计，并留下可复核的PPA增量；二是执行、产物、事实和交接集中管理，Codex只需依据结果决定下一步。最终采用更好的分支，不要求最后执行的Agent覆盖前面的成果。

## Evidence map

- Full measurements: [CSV](INVITED_PAPER_METRICS_20261020.csv).
- Figures and acceptance scope: [current results](INVITED_PAPER_RESULTS_20261020.md).
- Existing G02 validation: `var/business/a29-paper-delivery-20261020/gcd-retained-package/manifest.json`.
- DG1 validation: `var/business/a29-paper-delivery-20261020/runtime/experiments/gcd/a29-gcd-dpl01-goal01-validated-r1/validation.json`.
- DG1 final facts: `var/business/a29-paper-delivery-20261020/gcd-dpl-goal-all-final-sdk-facts.json`.
- Actual handoff: `var/business/a29-paper-delivery-20261020/gcd-dpl-goal-handoff-inheritance.json`.
- Decision to retain G02: `var/business/a29-paper-delivery-20261020/gcd-dpl-goal-next-decision.json`.
- Platform interfaces and operation trace: [record](A29_PLATFORM_OPERATION_TRACE_20261020.md).

DPL/ReviewDSE, GoalEvolve, and TimingECOAgent retain their original research attribution; this text describes platform integration and the measured cases, not a claim to invent the integrated optimization algorithms.

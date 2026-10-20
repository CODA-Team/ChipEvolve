# ChipEvolve 论文方法与图注素材

状态：2026-10-20 的已完成证据；新增GCD DPL01→Goal原1×4及完整验证已完成，原DPL三Student轮次和ibex仍在运行，JPEG24GiB证明在分区阶段超时，未采用该候选；Ariane原网表/含宏floorplan完整ORFS已实际运行。本文是工程方法说明和可核查表述素材，不是四设计实验已经完成的声明。数值与来源见[实测表](INVITED_PAPER_RESULTS_20261020.md)，实际接口见[操作记录](A29_PLATFORM_OPERATION_TRACE_20261020.md)。

## 平台方法

ChipEvolve为现有Codex提供芯片领域能力。Codex负责规划、解释证据和选择下一步；平台负责专业任务接入、确定性执行和设计事实访问。平台包含执行底座EF、数据底座DF、作为契约与SDK的DI，以及复用宿主推理能力的Query。它没有另建通用Agent harness、评测数据库或必须使用裸模型API的入口。

EF管理实验生命周期、线程/内存预约、实际工具进程、日志与原始产物；DF解析已登记的结果，按设计、修订、run及阶段快照组织指标和对象事实；DI提供带范围的查询和原件访问；Query以这些事实形成证据引用、观察和待检验假设，输出下一专业能消费的上下文。最终是否采用候选，由Codex依据领域目标和现有证据判断。

交接包保留设计身份、父run、约束/测量条件、专业策略/源码引用、检查点、产物SHA和Query上下文。不同专业使用适合自己的物理阶段：Flow产生配置及保存的阶段状态；DPL消费详细布局前的真实检查点；Goal消费明确设计状态并进行原生源码演化；ECO消费布线状态。回到较早阶段时，后续CTS/布线需要重新完成，不能声称它继承了旧最终线路；已完成且原生DRT为0的布线结果直接提取和测量，未收敛结果则另行完成必要布线。原生操作和交付补全的结果分列。

## 实际交接继承与重建

以下是已完成GCD分支的实际语义，不增加运行前置门禁。交接文件及摘要复核见运行记录`gcd-dpl-goal-handoff-inheritance.json`。

|交接|保留什么|重建或改变什么|源码如何处理|
|---|---|---|---|
|Flow F37→DPL|原Flow归档中的详细布局前检查点、设计身份、约束、原参数与来源|DPL执行真实详细布局；后续共同流程重新完成CTS和布线|DPL在自己的原生Teacher/Student工作区演化布局源码|
|DPL01→Query→Goal|实际DPL完成分支的单元、连接、设计状态、约束及有证据的Query上下文|Goal准备明确移除filler和信号线路，再执行原生优化/布线；旧寄生不能当成新结果|本次Goal从独立prepared seed开始；DPL源码引用保留在来源中，未自动合并进Goal源码|
|G03→ECO|实际G03布线结果、目标、时序问题和上下文|原生ECO动作可以改变单元和局部线路；本例未完成的DRT另作独立布线补全|使用ECO原会话和动作机制，不替换前两者的原生搜索|
|最终结果→Codex|共同测量、DF事实、原件引用、父子身份及有效功能证明|Codex比较并选择incumbent；无收益/不合法分支继续保留记录|源码晋升与最终业务采用分别记录|

因此，本轮证明的是专业间的设计状态接力及可追溯决策。没有自动组合多个研究项目全部C++改动，也没有宣称回到较早物理阶段后仍保留先前最终线路。

## 专业能力与接受规则

|专业|保留的原研究能力|本轮真实范围|
|---|---|---|
|Flow / A2-ORFO|原参数域、搜索和模型决策|GCD已有完整搜索直接复用；JPEG旧搜索按老板决定停止|
|DPL / DPLEvolve（ReviewDSE同一项目）|原Teacher/Student源码优化，Diamond/negotiation/framework三基线，原HPWL与运行预算|新增GCD原1轮3 Student；Student01已完成，整轮Teacher尚未收尾|
|Goal / GoalEvolve|原AST/EPD、Teacher/4 Student、专业机制及评分/晋升|既有GCD F37→Goal已完成；新增DPL01→Goal原1轮4 Student及完整验证已完成；ibex原1轮4 Student继续|
|ECO / TimingECOAgent|原生会话、动作、评分、best选择及回滚|GCD G03→ECO八轮完成，随后单列完整布线补全|

专业内部排序与平台最终接受分开。DPL降低HPWL，不保证最终功耗、面积和时序同步改善；Goal或ECO产生的中间态也可能仍有待修复的时序债务。允许从这种中间态继续探索，原合法incumbent保持，只有最终结果通过原约束并有相应功能证据才采用。既不重写原研究的晋升结论，也不默认采用最后一棒。

策略调节使用原项目已有选项，并在新实验开始前记录。新增GCD Goal保持80%功耗回收；ibex采用20%早期回收。ibex初次受保护power-only阶段因原电气门禁停止后，切换已有adaptive_tradeoff/power_then_timing以包含时序清理；保留失败和成本，不把切换当成已解决电气问题。没有改变最终硬约束或通用生成“功耗下降10%”目标。

## 测量与结果解释

共同最终指标包含功耗、cell/core/die面积、setup/hold WS与TNS、电气/布局违反和原生DRT计数，并附测量条件、run、来源SHA及父子关系。WS为原始最差余量，允许正值；规范WNS为min(0,WS)。当前GCD/JPEG/ibex分别采用ASAP7 FF、310/545/900ps。Ariane使用原研究提供的ASAP7映射网表、固定宏floorplan及SRAM模型，已完成导入，完整ORFS任务已实际运行，不能填写尚未完成的布线PPA。

论文可报告GCD的真实增量：Flow F37的0.89091155678mW、44.8918um²，经过Query→Goal后，G02为0.71564863902mW、39.1181um²，功耗下降19.6723%、单元面积下降12.8614%，同时修复父项面积超限，最终setup WS为+0.0834055ps、TNS0。G02已有全部18数字输出PDR、独立完整DRT/RCX七指标同值和公共SDK核验；相同产物的有效证明复用。

新增的DPL01→Query→Goal DG1最终为0.81929122098mW、39.6139um²、setup WS+1.31586ps/TNS0、hold WS+34.0384ps/TNS0，原生DRT及电气/布局违反均0；较实际DPL父项功耗下降12.6104%、cell面积下降11.9286%。全部18输出PDR、独立完整DRT/RCX七指标同值及公共DF/DI48值核验通过；三份兄弟候选setup拒绝。该分支展示实际Flow→DPL→Goal交接后的合法结果，旧G02仍更低功耗并保留；本分支TNS已闭合，没有为凑串行四棒再发ECO。新旧Goal分支使用不同阶段/策略，不能把结果差异全部归因于DPL。

G02相对ORFS B0参考的功耗/单元面积降幅为47.8980%/8.3364%，但整条链包含不同综合/方法来源，不能把这两个百分比全部归为专业协同的独立因果作用，也不能据此宣称优于所有最佳单Agent。

两个真实拒绝例可以说明决策与追踪能力：DPL Student01的HPWL由Diamond参考536.9um降至530.9um，但最终0.93751552049mW、44.9793um²，比实际F37父项更差且面积超限；G03→ECO八轮将绝对TNS违例量减少69.0726%，仍未闭合且原生DRT54，补全布线后DRT0而TNS仍为−0.266838ns，故未替换G02。拒绝分支是实际实验记录，不是编造的失败对照。

独立`drt::check_drc`的marker与原生详细布线计数采用不同方法，当前分别保存，尚不宣称两者等价或达到独立签核。平台效率先展示实际操作和可测成本；没有同任务对照时，不写token或墙钟节约率。新旧专业轮次、模型缓存token、EF采样CPU及宿主推理的范围分别说明，不将未知费用置零。

## 可用英文图注

**Architecture.** ChipEvolve exposes physical-design capabilities to Codex through a shared execution foundation and design-fact interface. The execution foundation manages tool processes, resources, logs, and artifacts; the data foundation and interface expose scoped design facts; Query preserves evidence and handoff context. Codex retains planning and acceptance decisions. The integrated professional algorithms remain attributed to their original projects.

**Measured GCD relay.** The retained Flow F37 → Query → Goal G02 branch reduces power by 19.67% and cell area by 12.86% relative to its actual Flow parent while satisfying the final constraints. DPL and ECO are shown on their actual exploratory branches, including rejected outcomes and separately measured routing completion. Pending steps are marked explicitly; the figure does not imply a successful serial chain through all four professionals. ORFS B0 is a reference comparator, not an invented direct ancestor of F37.

**Additional validated relay.** The saved Flow placement is consumed by DPL; its completed Student01 layout is measured and diagnosed before Goal optimization. Goal DG1 reduces final power by 12.61% and cell area by 11.93% relative to this actual DPL parent, satisfies the final constraints, and passes all-output equivalence and an exact independent routing replay. The earlier G02 remains the lower-power incumbent. This is a distinct measured branch, not a matched ablation of adding DPL.

**PPA table.** Completed measurements are reported with their design, parent, measurement condition, artifact identity, and acceptance status. Positive worst slack is denoted WS; canonical WNS is reported separately in the accompanying machine-readable table. Incomplete experiments have no substituted PPA values. Cross-method end-to-end differences and within-branch improvements are distinguished.

## 来源与可核查入口

DPLEvolve/ReviewDSE与GoalEvolve分别引用CODA-Team原项目；TimingECOAgent引用ASU-VDA-Lab原项目及保留的NOTICE。模块适配提交由`SOURCE_MANIFEST.json`固定，具体实验使用各自冻结源码和二进制身份，不把最新版工程提交当成历史实验版本。专业算法本身不是平台集成工作的新增原创贡献。

- 原项目：<https://github.com/CODA-Team/DPLEvolve>、<https://github.com/CODA-Team/GoalEvolve>、<https://github.com/ASU-VDA-Lab/TimingECOAgent>。
- 本机阅读PDF：`var/business/a29-paper-delivery-20261020/paper-assets/teacher-review-overview-r5.pdf`。
- 原始结果/验证快照：同目录`teacher-review-snapshot-r5.zip`，含逐文件SHA；本文可与该已完成结果快照共同审阅。

# 邀请论文实验素材：当前实测版（2026-10-20）

这是持续更新的实验素材，不是声称四设计已经全部完成。当前19行数据从原结果逐SHA核对后导出；新GCD DPL原轮次仍在执行；Student01→Goal原1轮4Student已完成最终测量，新增合法分支通过18输出PDR和独立重放；未完成候选不填结果。CSV包含完整PPA、电气/布局违反、DRC方法、run/条件/目标及来源SHA。

## 当前可用结论

GCD已有真实 Flow→Query→Goal 合法增量：相对实际Flow父项，功耗下降19.6723%、单元面积下降12.8614%，并修复父项面积超限。Student02有18输出PDR和独立完整DRT/RCX七值同值；Student01保留更大时序余量。

JPEG保留可行Flow候选及真实负接力。DPL Student03仅原cell面积上限失败；不事后改写约束。原Goal03→ECO的时序与功耗退步如实展示，该旧ECO交付包含平台重布线，不能拿它代表修复后的交付效果。

新增真实 Flow F37→DPL01→Query→Goal DG1 合法分支：0.81929122098mW /39.6139um²，setup WS+1.31586ps/TNS0，DRT及电气/布局违反0。较实际DPL父项功耗−12.6104%、单元面积−11.9286%；全部18输出PDR、独立完整DRT/RCX七值同值及DF/DI通过。G02功耗仍更低，保持保留。两条Goal分支的阶段/策略不同，不把分支差异当作DPL的独立因果效果。

## 已有测量

|设计|节点|专业|功耗mW|cell µm²|setup WS ps|setup TNS ns|状态|
|---|---|---|---:|---:|---:|---:|---|
|gcd|B0|ORFS|1.373553765000|42.6757|9.34292000|0|reference|
|gcd|F37|Flow|0.89091155678000|44.8918|12.289000|0|handoff; area exceeds limit|
|gcd|G01|Goal|0.75559981633000|39.2348|5.31003000|0|retained alternative|
|gcd|G02|Goal|0.71564863902000|39.1181|0.0834055000|0|adopted|
|gcd|G03|Goal|0.76853850624000|38.7974|-70.4802000|-0.856145|rejected: setup timing|
|gcd|G04|Goal|0.76625181828000|38.9869|-92.9781000|-1.01305|rejected: setup timing|
|gcd|GE8|ECO|0.77087164391000|38.9432|-32.4331000|-0.264783|rejected: setup timing and native route DRC 54|
|gcd|GEC|route completion|0.77061523916000|38.9432|-32.4934000|-0.266838|rejected: setup timing; complete route DRC0|
|ibex|IB0|ORFS|29.243746772000|2403.75|25.478000|0|reference: complete flow; explicit multi-VT libraries|
|gcd|D01|DPL|0.93751552049000|44.9793|10.4943000|0|area rejected; exploratory Goal repair branch submitted; native Teacher pending|
|gcd|DG1|Goal|0.81929122098000|39.6139|1.31586000|0|validated feasible alternative; G02 retained|
|gcd|DG2|Goal|0.8015136118000|39.1473|-85.4511000|-0.867528|rejected: setup timing|
|gcd|DG3|Goal|0.80402684398000|39.1473|-93.1683000|-0.98939|rejected: setup timing|
|gcd|DG4|Goal|0.80402684398000|39.1473|-93.1683000|-0.98939|rejected: setup timing|
|jpeg|JB0|ORFS|178.33724618000|6734.18|19.5042000|0|reference|
|jpeg|JD3|DPL|178.1052202000|6735.09|19.8262000|0|rejected: original area limit|
|jpeg|JF10|Flow|176.39359832000|6712.36|6.83587000|0|measured feasible; old partial search|
|jpeg|JG3|Goal|150.8680135000|6243.33|-12.5853000|-0.0701142|rejected: setup timing|
|jpeg|JEold|ECO|151.72357857000|6243.36|-12.9088000|-0.170005|rejected: setup timing; legacy platform reroute|

完整字段：[机器可读指标表](INVITED_PAPER_METRICS_20261020.csv)。GCD条件为ASAP7 FF/310ps，JPEG为ASAP7 FF/545ps，ibex为ASAP7 FF/900ps；跨设计不直接计算改善率。ORFS对照与现代Flow综合/方法来源分列；相对ORFS的全部降幅不归为某段源码或协同的唯一贡献。

## GCD实际接力与本轮动作

```mermaid
flowchart LR
 F[Flow F37：已完成] --> Q[Query：已完成]
 Q --> G[Goal一轮四Student：已完成]
 G --> G2[G02：合法并保留]
 G --> G3[G03：时序失败]
 G3 --> QE[Query：定位反相器与12负载]
 QE --> E[ECO八轮完成：TNS改善69.07%，未闭合且DRC54]
 E --> R[完整布线补全：DRC0，仍setup拒绝]
 F --> D1[DPL Student01：最终PPA已测，面积拒绝]
 F -. 同原生三Student轮 .-> D[DPL其余候选：进行中]
 D1 --> QD[Query：HPWL与PPA冲突诊断]
 QD --> GN[Goal一轮四Student：完成]
 GN --> DG1[Student01：合法且完整验证通过]
 GN --> DGX[Student02/03/04：setup拒绝]
```

实线表示已完成的真实步骤；虚线标明当前计算或后续步骤。DPL整轮仍在执行，Student01经Query→Goal已形成新的合法验证分支；ECO是真实完成的拒绝侧枝，不画成成功采用的四棒主线。

## 平台做什么

```mermaid
flowchart LR
 C[Codex：目标与决策] --> Q[Query：事实调查与交接上下文]
 Q --> DI[DI：公共SDK]
 DI --> DF[DF：设计与实验事实]
 C --> A[Flow / DPL / Goal / ECO]
 A --> EF[EF：执行、资源、状态、产物]
 EF --> T[OpenROAD / ORFS / 源码构建]
 T --> EF
 EF --> DF
 DF --> Q
 Q --> C
```

本轮G03 Query已查询实际DF快照并导出专业上下文：4事实/4假设，定位reg2reg关键路径、共享小SLVT反相器及12负载，建议增强驱动/分裂负载；没有把建议冒充已执行或因果证明。ECO由平台派发，原专业评分与回滚保留。实际八轮最终功耗0.77087164391mW、cell面积38.9432um²、setup WS−32.4331ps、TNS−0.264783ns；相对G03绝对TNS减少69.0726%，但仍未闭合且原生DRT54，所以原生分支拒绝，合法G02不变。随后单独完成原方法仅一轮DRT所留下的布线违反，DRC54→0、功耗0.77061523916mW、setup WS−32.4934ps/TNS−0.266838ns，仍时序拒绝；不重跑模型，补全前后分列。

## 当前四设计交付状态

|设计|当前交付|下一步|
|---|---|---|
|GCD|合法既有成果已固定；DPL原轮次继续；Student01→Query→Goal新增合法分支0.819291mW/39.6139um²，18输出PDR/独立重放通过；ECO侧枝仍setup拒绝，G02保持|收齐原DPL轮次；新合法分支判断是否还有必要动作，保持G02低功耗成果|
|ibex|完整ORFS基线及三事实入库完成，原约束全通过；Query4事实/1假设完成|首power-only基线因469 slew拒绝；原adaptive功耗+时序阶段已通过Teacher规划并进入四Student，20%回收保留|
|jpeg|旧可行候选与真实负接力可复用；老板已停止低收敛第二轮余下搜索|按已有结果诊断选择有效起点，不重跑整个搜索作为前置|
|ariane|已找到原Goal ASAP7 placed基准：210295组件、136 SRAM实例、21 Liberty/11 LEF，宏模型存在|原布局已由EF成功导入并核对210295组件/136 SRAM；原映射网表+floorplan的完整ORFS配置已准备，待GCD资源后执行；不称原样ORFS RTL基准|

## 指标与证据口径

表中WS是原始worst slack，可为正；CSV另列规范WNS=min(0, WS)。原始结果不改写。最终采用按原setup/hold、功耗、面积、布局/电气及原布线流程DRC条件判断；缺失值写unknown。工具估计PPA不等于硅测或全工艺签核。JPEG Flow10功能证明本次因8GiB预约不足而中止，未证明、未采用；24GiB重试已作为新case进入EF排队，不重开搜索。

DPL Student01原生HPWL530.9um（较Diamond536.9下降1.1175%，较framework531.9下降约0.188%），但最终功耗0.93751552049mW、cell44.9793um²，较实际F37父项功耗/面积更大且面积超原上限。Query已以真实四事实/三假设导出交接上下文，新Goal一轮四Student从该布局分支出发，Student01最终0.81929122098mW/39.6139um²，setup WS+1.31586ps/TNS0，DRT及电气/布局违反0；较DPL父项功耗−12.6104%、cell面积−11.9286%，通过全部18输出PDR、独立完整DRT/RCX七值同值和SDK核验。其他3候选setup拒绝；旧G02仍更低功耗，继续保留。新旧Goal分支的阶段/策略不同，不能把分支差异全部归因于DPL。

新增保留布线实测已确认相同线路/单元/引脚及七PPA不变。独立`drt::check_drc`返回5377 marker，而原DRT流程计数为0，两者方法不同，独立检查值另列，不偷偷替换原指标或宣称它们等价。新ECO会在原生best选择时保存当次DRT计数，并与实际交付ODB哈希绑定；完整本轮验收见A29施工记录。独立marker的物理含义尚待专项核实，本文不宣称独立检查为零。新ECO独立checker为5924，另列；原生54从最佳选择的原始控制台记录恢复并随EF归档登记。原输出目录建立过晚的缺陷已在未来版本修复，当前实验没有重跑模型或篡改其原生动作。

平台效率先报告实际操作链、成功交接及已知成本；没有同任务对照的数据，不填写token/时间节约比例。研究算法按上游归属引用，平台贡献是统一集成与协同环境。


## 本机论文图件与方法说明

新增PPA图：`var/business/a29-paper-delivery-20261020/paper-assets/gcd-ppa-observations-r2.pdf`（另有SVG）。从CSV选择7个已完成GCD节点，逐原件SHA核对，标明原面积上限、合法采用与拒绝状态；横向排列不是连续接力。完整节点仍以CSV为准。

更新后的GCD实际接力图：`var/business/a29-paper-delivery-20261020/paper-assets/gcd-measured-relay-r2.pdf`（另有SVG）；DPL01→Goal新合法分支已由虚线待做改为实线完成，既有ECO拒绝侧枝保留。

[方法与英文图注](INVITED_PAPER_METHOD_NOTES_20261020.md)说明平台分工、阶段交接、专业能力、采用规则和比较范围。

JPEG独立追踪图：`var/business/a29-paper-delivery-20261020/paper-assets/jpeg-measured-relay-r1.pdf`（另有SVG）。五个历史实测节点及三个真实父子交接已由input-receipt的source原件SHA核对；Goal03→ECO负接力保留，旧ECO交付重布线标明，Flow10单独列示，不推断其父边。

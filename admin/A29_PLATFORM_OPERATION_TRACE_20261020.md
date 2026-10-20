# A29 平台操作与接口实证

平台让当前 Codex 调用领域能力，统一提交实验、登记产物、取得设计事实；是否继续、接受哪条分支由 Codex 判断。下列记录来自本机实际调用，不是 token 节约率或四专业连续成功的声明。

## 已完成的操作

|操作|实际结果|原件（根目录下）|
|---|---|---|
|固定 GCD 已采用结果|复用 G02 的原验证，不重跑相同产物|`var/business/a29-paper-delivery-20261020/gcd-retained-package/manifest.json`|
|读取设计状态并诊断|G03 的 Query 完成4事实/4假设，定位共享反相器及12负载|`var/business/a29-paper-delivery-20261020/gcd-eco-source/query/professional-context.json`|
|当前 Codex 判断两候选|2次 DF 事实读取、引用各自证据、回答保留 G02；额外 Query 内部模型调用0|`var/business/a29-paper-delivery-20261020/same-codex-query-demo-r2/answer-state.json`|
|同一布线产物交付|组件/线路/引脚 DEF 段完全相同，七项 PPA 精确同值|`var/business/a29-paper-delivery-20261020/preserved-routing-acceptance-r3.json`|
|提交实际专业任务|DPL 两个候选完成首轮构建和评价并继续原生调整；ECO八轮及共同测量/事实交付完成，按setup/DRC拒绝|本轮 `runtime/experiments/gcd/` 的原生/EF回执|
|导入较大含宏设计|原 Ariane ASAP7 placed 基准经 EF 导入成功，210295组件及136 SRAM均核对|`var/business/a29-paper-delivery-20261020/runtime/experiments/ariane/a29-ariane-original-placed-import-r1/import-result.json`|

同一 Codex 展示的初始化和两次读取墙钟约1.346秒。父 Codex 的推理 token 没有单独计量，不能把“额外内部模型调用0”写成“总 token 为0”。旧64KiB调查预算失败的记录保留；完成案例使用512KiB预算，实际读取约50KiB。

## 接口与责任

接口取自现有实现，表中参数省略非核心可选项。DI 是安装的 SDK，没有另建服务。

|调用者→模块|现有签名或入口|返回/责任|
|---|---|---|
|Codex→业务入口|`chip-evolve.py --config CONFIG run --design DESIGN --capability dpl\|goal\|eco --source RESULT --context CONTEXT --rounds N --seconds N`|准备原生输入并提交；输出结果或具体失败|
|专业接入→EF|`KernelClient.submit(task, idempotent=True, idempotency_key=key)`；`POST /kernel/runs`|`run_id`、任务状态；工具进程由EF监督|
|Codex/接入→EF|`KernelClient.run(run_id)` / `logs(run_id, offset=0, max_bytes=...)` / `resources(run_id)`|状态、日志、预约和实际用量；资源等待与工具失败分开|
|接入→DF|`POST /snapshots/from-run`，请求含`run_id, artifact_id`|解析已登记的事实归档，保存导入回执|
|Codex/Query→DI→DF|`EdaAiClient.resolve_scope(snapshot_id=...)`；`GET /scope`|确定唯一设计/版本/实验/阶段快照|
|Codex/Query→DI→DF|`get_stage_summary(snapshot_id)`；`GET /snapshots/{id}/summary`|对象数量、覆盖范围和来源|
|Codex/Query→DI→DF|`get_metrics(snapshot_id=..., include_raw=True)`；`GET /snapshots/{id}/metrics`|指标、单位、条件及证据；分页|
|Codex/Query→DI→DF|`get_timing_paths(snapshot_id, check="setup", sort="slack", order="worst", limit=5)`|明确范围的最差路径样本，不冒充全量路径|
|当前 Codex→Query|`query_agent investigate ... --model host`，随后`act INV --decision FILE --model host`|复用已具备推理能力的宿主；Query保存调查和证据关系|

最小交接数据包含：`design_id`、`run_id`、`snapshot_ids`、`condition_id`、`objective_id`、原件身份及SHA、事实/假设、目标、允许动作、预算。实际字段以 `result.json` 和 `professional-context.json` 为准。这里没有增加另一份可写的“真相库”。

```mermaid
flowchart LR
 C[Codex 决策] --> Q[Query 调查及上下文]
 C --> A[Flow / DPL / Goal / ECO]
 A --> EF[EF 执行、资源、原件]
 EF --> T[EDA 工具]
 T --> EF
 EF --> DF[DF 解析、设计事实]
 Q --> DI[DI 公共 SDK]
 DI --> DF
 DF --> Q
 Q --> C
```

```mermaid
sequenceDiagram
 participant C as Codex
 participant Q as Query + DI
 participant D as DF
 C->>Q: 固定 G02/G03 快照，读取最终指标
 Q->>D: 两次带范围的 metrics 读取
 D-->>Q: 指标、单位、条件、证据
 Q-->>C: 事实与引用
 C->>Q: 保留 G02，G03 作为 ECO 探索
 Q-->>C: 持久化证据回答
```

```mermaid
sequenceDiagram
 participant C as Codex
 participant A as 专业接入
 participant E as EF
 participant T as OpenROAD
 participant D as DF
 C->>A: G03 + Query 上下文 + 原约束
 A->>E: 原件身份、线程/内存、原生会话
 E->>T: 调度并监督工具进程
 T-->>E: 结果、日志、原件
 E-->>A: 登记产物及用量
 A->>E: 必要提取及共同测量
 A->>D: 导入已登记事实
 D-->>C: 供后续诊断及接受/拒绝判断
```

后一图的本轮ECO调用链已实际完成：共同PPA与公开SDK一致，原件及恢复证据登记完整；业务约束未通过，保留G02。执行成功和业务采用分别记录。

## 关键决策

- 原件与实验生命周期归 EF；解析后的设计事实、索引和查询归 DF；DI保持 SDK。Codex不用直接读服务内部数据库或管理工具进程。
- DPL 消费实际布局检查点，ECO 消费实际布线状态，避免统一成一个会丢失专业能力的假输入。
- 已布线 ECO 交付保留线路，只做提取与测量；未布线检查点仍需完成布线。独立checker的marker与原生DRT计数分别保存，目前不能声称它们等价或独立DRC为零。
- 专业局部排名和最终业务约束分开：允许有待下一棒修复的中间态；最终采用不能绕过原约束，也不默认采用最后一棒。
- 本机资源按实际设计配置。当前运行ECO仍使用已冻结的24GiB预约；新接入支持后续显式声明内存，不为启用新选项打断正在运行的实验。
- Ariane使用原研究提供的ASAP7 placed基准及SRAM模型，明确区别于ORFS RTL起点；目前只完成导入，不填写完整布线PPA。

## 2026-10-20 16:03 增补

DPL Student01已真实完成最终CTS/route并经DF/DI七项核验：原生HPWL降低没有转化为最终PPA改善，按原面积限制拒绝。Query实际形成4事实/3假设后，Codex从这个可修复中间态发起原Goal一轮四Student，原G02仍保留；EF登记原生candidate-brief并公开取回核对SHA，专业原排名未更改。这里同时展示“派发→执行→事实→调查→再派发”和拒绝无益分支的实际过程。

ECO八轮及随后独立完整布线已完成，后者原生DRT54→0，但setup仍失败；未来交付只有明确DRT0的已布线状态才保留线路，未收敛检查点正常补全。本轮不再有活动ECO会话。GCD的CTS/route内存声明4GiB已实测消费，其他设计按自己的配置申请。

老师审阅材料已生成本机ZIP快照，当前含15个完成节点；运行中的候选不计作成功。调用成本仍按原证据范围列出，不以缺测量的总token/时间节约率替代实证。

## 新增三专业合法接力：Flow→DPL→Query→Goal→DF/DI→Codex

已完成DPL01→Goal原一轮四Student和共同交付：DG1为0.81929122098mW/39.6139um²，setup WS+1.31586ps/TNS0，hold WS+34.0384ps/TNS0，原生DRT、电气/布局违反均0；较真实DPL父项功耗−12.6104%、cell面积−11.9286%。全部18输出PDR和独立完整DRT/RCX七指标精确同值通过；四份最终候选共48个raw值及快照身份通过公开DF/DI SDK。另3份setup拒绝，完整保留原生评分和源码引用。

Codex据此保持原G02低功耗结果，将DG1归档为经过验证的合法接力案例。本分支时序已经闭合，下一步不为串行展示额外派发ECO；此前G03→ECO八轮和独立布线补全仍是真实参与记录。实际读数、比较、验证与决定见本轮`gcd-dpl-goal-{all-final-sdk-facts,next-decision}.json`及`a29-gcd-dpl01-goal01-validated-r1/validation.json`。旧G02与新DG1策略/阶段不同，不把两者差异写成隔离的DPL贡献或最佳单Agent对照。

## 三设计业务状态与排队原因的实际查询

沿各实验实际使用的冻结入口，分别执行现有`status --design ariane/ibex/gcd`，并对ibex后续run执行`watch --design ibex --run-id ...`。三份状态回复分别684/2051/2182字节，watch回复2307字节；这是真实返回体大小，不是节约率或大模型token数量。

- Ariane：直接返回正在运行的完整ORFS实验及`run-c40e2257df494a38a1d941901dfc8952`。
- ibex：直接列出历史失败、已成功基线和原Goal进行中状态；watch将`run-c86add5b87444698b4c566157bce5b64`明确分类为`resource_wait`，说明需要12GiB、当前预算剩0，kernel仍新鲜并在执行其他任务。
- GCD：新增Goal接力及其验证均为succeeded；原DPL三Student轮次仍in_progress。

这些问题通过现有业务入口与公开EF查询完成，无需调用者直接查询内部数据库或检查物理目录。执行状态由EF负责；设计PPA和诊断事实仍走DF/DI/Query，二者职责不混用。父Codex负责解释回复；额外内部模型调用0，父推理token与同任务节约比例未计量。

不可变回复、原文件摘要及本轮解释保存在`var/business/a29-paper-delivery-20261020/business-status-demo-r1/answer-and-evidence.json`及同目录四份回复。这是一份带观察时点的操作快照，不把其中running或queued状态当作永久事实。

## JPEG源状态调查与后续决策准备

现有`diagnose --result Goal03 --against oldECO`完成真实调查并导出`jpeg-goal03-source/query/professional-context.json`。调用者明确source/reference的祖先关系，Query通过DF/DI查询七PPA、全组最差路径排序、对象与连接，返回4事实/3假设及局部WNS与全局TNS冲突证据。根Codex据此准备下一次原生ECO，保留原专业动作选择和评分，尚未派发；原停止Flow搜索没有恢复。

Query在有界读取中无法从gzip片段验证Liberty，且两份完整SDC尚未比较；根Codex随后使用公开DI一次取回登记原字节、核对SHA并解压/比较。SDC有效指令文本相同，HA声明已提取，结论保存独立补充记录，未篡改原调查结果。这个过程展示平台事实与通用Codex判断配合，也记录当前查询封装仍有改进余地；不把每个查询限制变成实验前置门禁。本次host确有模型调用，既有确定性status读取的“内部调用0”口径不能套用到这里。

## Ariane停止附带检查后的统一观察

`business-status-demo-r2/answer-and-evidence.json`冻结再次真实调用的Ariane status/watch及SHA。原任务business状态为failed，内层EF明确cancelled；新的已完成物理检查点续接为in_progress，watch显示resource_wait，需要16GiB、当时预算剩12GiB，kernel正在执行原GCD/ibex任务。用户可通过相同入口分辨“附带检查被主动停止”和“新测量在资源等待”，不用读取内部数据库。

这次一次性续接调用现有执行/测量/发布函数，尚未提供业务request的capability标签，因此status按既有缺省显示validation；其operation、原run与精确EF句柄已在收据说明，不能冒充一次新的专业优化或完整ORFS成功。原生LEC与最终事实交付耦合仍是后续可简化的接点；本轮先保存实际产物并接续，不扩建框架。确定性status/watch未额外调用模型，父Codex解释用量未知，未测节约比例。

## 2026-10-20 23:01 本轮最新核查（覆盖上文历史进行中口径）

- GCD原DPL一轮三Student与Teacher已完成，原生选中Student02；其共同CTS/布线交付仍排队。Student03合法化在原定时间内未结束（124），框架按原规则保留失败并完成轮次。已验证的DPL01→Goal DG1不改父项，保留功耗更低的G02。
- ibex原Goal一轮四Student与Teacher已完成，晋升Student01修复版。主分支最终为28.18046324mW /2339.71µm² /setup WS−28.3996ps /TNS−1.59699ns、slew32/cap1，不采用；12原始指标和三快照身份已通过DF/DI核对。其余候选共同交付排队。
- ibex主分支Query已完成，证据支持检查`_17624_`共享逻辑与`place4192`/`place4191`输出缓冲；故准备独立原生Goal timing-only修复。沿用已测网表/布局与900ps/库/SDC，原生prepare清除信号线和fillers、之后完成原详细布线；不把修复隐藏在测量里，不称Student01 C++源码已自动合并到新执行文件。当前只准备，尚未派发。
- ibex后续`run-58bdc4163b2940a796f3621ca48b1108`已通过EF原请求更正为**同源码last_gasp_deep匹配基线**，不是repair2。公开原件SHA核验显示该基线与Student03/04的ODB/V/DEF逐字节一致；不能声称这两个深策略已产生原生QoR收益。
- Ariane完整物理参考的RCX、共同测量及三类事实已经完成：642.41528511mW /43672.8µm² /setup WS−285.396ps /TNS−155.146ns /slew436，原生DRT0。1800秒事实导出成功，12值/3身份通过。原ORFS inline LEC被明确取消、功能尚未证明，不称完整原任务成功。
- Ariane Query已完成并指出深标准单元reg2out逻辑时序问题，已派发原Goal timing-only/StrictEvidence一轮四Student；32GiB原生基线当前等待资源。该设计保留原SRAM模型，不宣称所有宏均FF或完整签核。
- JPEG旧Flow搜索保持停止。以原Goal03为父的新定向ECO会话实际运行，最多八轮；尚无新的共同最终PPA。保留原负接力与Flow10证明超时。
- 新源码固定00199d3：仅按实测时间配置Ariane共同物理收尾7200秒；既有默认1800秒不变。事实导出配置1800秒的修复bc89146已通过针对检查；最近根570回归和静态/格式/类型检查通过。两修改均只用现有内部设计绑定，不增服务/API/数据库。

本轮实测等待为内存预约冲突：JPEG20GiB运行时，GCD与ibex的**冻结共同物理请求各24GiB**、Ariane32GiB不能进入余下12GiB。ibex原生评价12GiB不等于共同收尾24GiB，不改动冻结任务或把等待写成派发丢失。

论文表已有21个SHA核对完成节点（含Ariane参考、ibex主结果），新r7审阅包将持续导出；未完成四设计收口，不声称协同全面优于最强单项或token节约比例。

### 23:22更新：真实成本与完成状态

JPEG定向ECO原生八轮完成、10次模型调用（两次重试），原生DRT9592；完整布线/共同测量已另行派发。只读成本导出同时纳入`session/execution.json`，覆盖此前漏在该子范围之外的两次ECO执行回执：当前181个已保存EF回执，采样CPU106157.51秒，仍不是全场费用。ibex主分支Query另记录input1558174、cached1423104（输入子集）、output10127、445.14秒。专业DPL五次完成模型调用的缓存输入也作为输入子集，子调用时长之和不当作campaign墙钟。未知货币费用和宿主推理不置零，不报告未测量节约率。

最新审阅入口：`var/business/a29-paper-delivery-20261020/paper-assets/teacher-review-overview-r8.pdf`，九页含四设计独立接力图、21完成测量节点和原生阶段诊断；`teacher-review-snapshot-r8.zip`保留结果逐字节副本及来源SHA。四设计尚未全部完成。

## 2026-10-21：同一Codex实际查询与继续派发

新ibex最终状态已由当前Codex通过Query host读取：两份完整metric包、setup/hold样本、所有已存setup组与最差路径engineering，共六次成功读取109190字节；四次path参数格式错误也保留为失败。Query保存了新调查、原件引用与professional-context后，原生收尾脚本消费该新上下文，通过现有Jobs/KernelClient提交实际SPEF/传播时钟下的native EDA动作和后续DRT/RCX/事实发布。没有额外Query子模型调用；223.63秒调查墙钟包含宿主步骤等待，服务内0.410秒不能替代总用时，父模型token未知。

调查确认setup同时涉及reg2reg和reg2out；所选路径cell/wire原增量仅支持机制，不是完整归因。新收尾r1的“原生报告闭合、最终仍失败”按真实结果保留，随后只针对明确发现的Resizer增量寄生初始化问题与路由后slack余量启动r2；原生算法及正式验收约束不改。JPEG同候选保留线路的RCX作为诊断，native DRT计数unknown，禁止采用。全部是已存在EF/DF/DI/Query能力的消费，没有新服务、数据库或API，也不把试验性native原语封装说成新的专业研究Agent。

## 10月21日01:24：新完成的实际闭环

1. 当前Codex基于先前Query的ibex诊断，显式派发带增量RC初始化协议的原生收尾；EF完整DRT/RCX后将最终设计登记到DF，DI复核十二原始指标及三快照身份。Codex因setup/slew失败拒绝采用，保留IB0。这一闭环并非“工具成功所以优化成功”。
2. JPEG同候选保留线诊断也经EF执行新RCX/测量，并通过DF/DI的十二值/两身份核对。Codex比较同原始ODB与同condition/objective后识别布线交付差异，派发一份直接读取既有线/guide的原生DRT任务。旧Flow搜索始终停止；没有重跑模型搜索，也未把未知DRC当零。
3. 当前成本快照`cost-snapshot-20261020T172412Z.json`包含242个闭合EF任务及采样CPU134263.69秒；专业Goal20份用量回执、DPL5次模型和既有Query范围分别保留。未闭合任务不填完整成本；缓存输入是输入子集，没有同任务对照或父Codex独立token计量时不计算节约比例。

## 10月21日03:37：失败也通过统一入口留证

Ariane原生7200秒超时后，EF保存完整输出、部分检查点、源码/输入声明和失败回执，原框架接续其他候选；JPEG既有线DRT也已真实消费输入并保存DRT1231失败。两者都不是队列丢失或DF查错设计。Codex据具体JPEG错误和已登记Query上下文调整为VT/size原生序列，新任务继续通过EF，保持原条件/目标和最终验收。失败没有最终设计事实时不伪造DF完整PPA快照，EF原件与公开日志用于过程追踪。新增失败表保留真实墙钟/采样CPU/内存，当前246个闭合EF的成本范围仍与整场墙钟、父Codex token分开。


## 2026-10-21 04:24：四设计统一状态入口与真实取消结论

以各设计当前配置实际调用冻结业务CLI的status；回复逐字节留存并核SHA，调用者未查内部数据库，也未启动新EDA或模型。旧Ariane已确认前端退出、两个EF句柄终态cancelled后，写入其管理状态cancelled及缺陷/替代实验引用；原输入、源码、已完成结果均未改。

|设计|回复字节|命令墙钟秒|
|---|---:|---:|
|gcd|2179|1.235480|
|ibex|3380|1.068880|
|jpeg|3235|0.686184|
|ariane|2535|0.361117|

四份回复能够直接区分GCD/ibex没有活动计算、JPEG最终布线与Ariane新基线实际运行，Ariane旧轮明确cancelled；不会将因缺少管理终态文件而默认显示的in_progress当成永久事实。状态负责回答任务在哪，PPA/诊断仍以DF/DI/Query及结果原件为准。

额外内部模型调用0，父Codex推理token未单独计量，未报告节约率。真实请求、输出和耗时在var/business/a29-paper-delivery-20261020/business-status-demo-r3/answer-and-evidence.json；本次是固定时点的观察，不把running当作完成。

更新的成本快照cost-snapshot-20261020T202410Z.json纳入前端被停止后无法自行落终态的两份公开EF取消收据，按run去重。当前254终态EF（240成功、7失败、5取消、2超时），采样CPU161397.19秒；20份Goal调用、五份DPL调用等范围分别列示。未包括的历史、父推理和服务开销保持unknown，不作为完整成本或同预算效率对照。


## 2026-10-21 06:22：Query诊断驱动一次新策略

当前Codex通过既有DI重新查询IP2，显式按slack全局排序后取得16条已存setup路径；最差reg2out路径与−0.00130401ns聚合值一致。有限路径不是全部端点，原生修复仍处理全设计。SDK默认路径分页未按slack排序，必须明确指定`sort="slack"`；`truncated`是有数据的分页状态，不能误判为调用失败。

根据JPEG新VT/size物理可行结果和IP2的23项slew违反，本次只新增一个明确的VT/size、30ps内部余量及修复前后10% slew margin策略。原900ps、最终零TNS/零电气违反要求不变，不声称源码合成。EF已接受run-ae7fbe43e69a4395b07b8c189035a248，父run/目标/条件、四原始输入SHA、完整Query上下文及实际Tcl均已核对；当前排队，尚无新PPA。只有本次原生策略或最终事实通过，才继续后续交付；没有自动重复循环。额外Query内部模型调用0，父Codex token未知。证据见ibex-ip2-query-new-strategy-r3/、ibex-ip2-vt-size-slew-r3-source-dispatch-audit.json。


## 2026-10-21 06:31：大原件取回与真实下一棒

JPEG最终网表证明run-0c55ea8898be432e8dc75f743cac18c4已由公开EF确认为succeeded。完整extractor_log为6,168,724字节，通过KernelClient.materialize_artifact取回本机并与EF登记SHA完全一致（4c36f256ccaf98c23fa35278553858b73f4508c36d3c61ffd40de727d1eac5c3）；没有把4MiB上限的内联字节接口当作大原件下载接口，也未读取私有状态库。完整证明27输出/7082分区及所有网表/Liberty哈希独立核对。

Codex随后复用实际PASS证明，只派发一次已记录物理交付的独立重放run-786929353c204058a30a502368e57c78。原repair输入ODB、PDK和实际交付路径由既有replay_checkpoint恢复，EDA经EF、事实经DF/DI；七指标一致及既有功能/采用检查通过后才调用select。原生修复、功能证明、独立物理交付和采用是四种不同事实，分别记录。

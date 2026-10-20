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

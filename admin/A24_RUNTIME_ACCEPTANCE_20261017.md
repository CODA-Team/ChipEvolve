# A24：本轮运行管理验收与JPEG接力现状

执行服务已原位更新，真实队列、取消、失败托管和GCD数据链路通过。JPEG时序接力仍不满足原约束，未采用；完整Flow校准、JPEG完整功能证明及正式公平对照尚未完成。以下是工程验证，老板业务验收独立。

## 当前运行环境

- EF为`942e0ef`，Toolkit为`688174b`；实际gateway与adapter两个wheel环境均与提交源码逐字节核验。EF PID为3663811，仍使用41151端口和原状态目录。
- DF保持PID2935255、43789端口、原主库/只读archive及配置；未部署用户未提交的DF/DI代码。更新前已备份原执行状态与两个wheel环境，文件位于本片`pre-update-backup/`。
- 当前账号内存组上限99,999,997,952 bytes，原服务配置128GiB超过此上限。内核明确记录JPEG证明的yosys PID2638022因该内存组OOM被杀。本次空闲检查测得账号工作集余量约42.55GiB，据此把本轮EF资源池设为32GiB，CPU仍32核；没有提高系统权限、改系统上限或停止其他会话。
- 后续新profile的Code构建预留32GiB，已测单LTO峰值约4.5–4.6GiB；Flow预留12GiB，已测最高约7.13GiB。原算法、参数域、Student数、评分及晋升保持。本轮新r4环境已冻结；活动副本和旧profile不改写。

## 实际检查

| 检查 | 实际结果 |
|---|---|
| 大任务资源不足时消费后方可执行任务 | 24GiB运行中、四个16GiB任务等待；2GiB真实GCD读取在其后成功完成，未超32GiB资源池 |
| 取消与资源释放 | 运行占位任务和四个等待任务均通过公开接口取消，全部达到终态 |
| 原失败与实际产物 | `run-3cebaaf295b3430083e7e44b4815f796`保留native退出23；日志可由注册artifact读取，缺失PASS列入manifest，不生成PASS或失败设计快照 |
| 更新后真实GCD共同测量 | `run-8d8b28cb00ef4eb5a511c4dfe16b8ebc`七项PPA与已验证来源逐值相同，三类DF快照及SDK核对通过 |
| 历史可查询性 | 原AES archive的SDK事实核对通过，原采用分支不变 |

队列/取消/失败托管实际组合约9.49秒。原生GCD读取通过也说明工具环境未因服务更新改变；七PPA同值是独立的共同测量验收。

本轮验证脚本的两次准备错误分别保留：第一次低层extractor未产出所需manifest，原GCD工具已执行但整个探针失败；一次GCD复测复用A23旧task名，被不可变TaskSpec检查以409拒绝，没有新EDA提交。改用标准业务leaf和A24独立实验名后通过。没有为这些脚本错误修改EF门禁或改写旧任务。

## JPEG接力的实际结果

| 同一FF/545ps条件 | 功耗mW | setup最差slack ps | 原约束 |
|---|---:|---:|---|
| canonical来源 | 178.33724618 | 19.5042 | 通过 |
| Flow完成分支45 | 172.81705141 | −15.7994 | setup TNS不通过 |
| 分支45→Goal原时序修复 | 172.35529423 | −20.1413 | setup TNS不通过 |
| 匹配无修复转换/布线控制 | 172.32514918 | −35.5112 | setup TNS不通过 |

Goal结果的完整共同测量、DF交付已成功，但最终TNS为−0.715618ns，不能采用或称为合法协同改善。实际专业阶段显示：`repair_timing`把原生估计TNS从约0.6565ns修至0，随后placement和global route重新引入违例；最终DRT/RCX测量也未闭合时序。阶段估计与最终测量口径不同，不直接相减归因。

该次调用是原Goal timing-only基线能力的固定接力，不是新的Code源码搜索；原Goal四Student轮次仍以原28800秒监督超时失败。原生互斥锁有意串行物理评价，Student3在等待评价时耗尽执行预算，不能称为EF吞掉任务。原算法和串行评价语义保留。

相同输入/二进制/转换/placement/route、仅省略修复调用的匹配控制已完成，四份结果均经公开DF/SDK逐项核对，Goal阶段证据也已登记。此次匹配比较中，原时序修复相对无修复控制改善最终最差setup slack 15.3699ps，功耗增加0.03014505mW，cell面积相同；整体仍不合格。Flow→Goal所见功耗下降不能全归给修复算法，转换/重布线控制本身已有下降。这是一次固定方法匹配观察，完整独立重放和新Code搜索分别验收。后续动作优先针对最终布线状态，不能凭局部TNS曾归零宣布整体通过，也不强制串联所有专业。

Query接点另发现两个不同ECO入口被混淆：Query内建`propose_handoff(role=eco)`/`EcoReceiver`仅消费明确cell/master权限的单缓冲器修改；ChipEvolve原生TimingECOAgent通过通用professional context及EF独立调度。前者无权限不能当后者不可用或未授权的证据。根`diagnosis.py`只澄清这项能力边界，不伪造权限、不移除原门禁，不在诊断中执行设计修改；修正后真实Query回验通过：新上下文`e88c1899...`正确面向调用者独立调度的原生TimingECOAgent，交付10条带证据内容、2条假设，确认实际最差reg2reg及相关数据锥，保留未执行/未验收与证据限制。未因内建小接口的权限拒绝推断原生ECO不可用。根383项回归与静态/类型/格式检查通过。

## 后续门槛

1. 完成当前匹配控制与阶段证据、SDK核对，选择有针对性的最终时序恢复，保留所有失败和合法分支。
2. 低内存策略的严格正反例已通过真实EF：EQY/SBY的ABC PDR、xprop开启，固定私有Z3 4.15.3负责反例重建；正确样例PASS，错误样例FAIL并有反例。记录了二进制、库与wheel指纹，未改共同镜像。根`eqy.py`仅增加私有`validation.equivalence_strategy=abc-pdr`和固定solver manifest选择，原SAT缺省、Liberty模型、输出和匹配规则不变，仍须所有分区PASS。八项新测试覆盖模型/匹配不变、身份篡改拒绝、完整覆盖和必需后端，原八项EQY检查一并通过；JPEG全量证明仍待新尝试。
3. 原两轮50候选完整Flow失败保持，新资源校准只允许一次新完整尝试：原两轮/50候选、完整参数域与阶段继承，单阶段8小时、总20小时上限，覆盖资源池缩小后的真实排队与计算，未启动则不得记成功。这不是正式公平预算。
4. A25再冻结模型/源码/预算/种子/顺序和账本，之后运行公平PPA与同Codex完整操作对照。当前没有证明团队全面优于最强单项或端到端token/时间优势。

运行证据为`production-update.json`、`production-queue-and-failure-r2/receipt.json`、`production-live-acceptance.json`、`environment-r4-receipt.json`、`candidate45-goal-relay-process.json`及`account-aware-next-stage-prepared.json`，均在`var/business/a24-jpeg-pilot-20261016/`。根最新已发布功能检查点`f5c4e08`的368项回归及静态/类型/格式门禁通过；本次PDR适配的16项针对检查、根376项回归和静态/类型/格式门禁通过，专业源码来源见根manifest。

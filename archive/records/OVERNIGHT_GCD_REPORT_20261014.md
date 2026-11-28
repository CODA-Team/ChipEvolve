# 本机 GCD 协同施工报告

状态：本轮工程验收完成，所有 EDA 会话和原生轮次已结束；老板业务验收待确认。验收回执：`var/overnight/gcd-20261014/final-acceptance.json`。

## 业务交付

| 老板要求 | 本轮实测 |
|---|---|
| 修好四专业能力的本机环境 | Flow / DPLEvolve / GoalEvolve / TimingECOAgent 在固定共同基础版本运行，各自专业源码和算法保留 |
| EDA 统一从执行底座启动 | 平台模式的阶段执行、构建、版本查询、专业测量及 ECO 持续会话交给 EF；失败不退回宿主 EDA |
| 统一管理与监控且不限制专业能力 | 任务身份、幂等提交、父运行、资源、日志、终态、产物、取消可查询；64 GiB / 2048 进程用于大构建，原专业内部循环保留 |
| 执行结果通到设计数据查询 | 注册产物导出对象 / 关系 / 指标 / 时序采样，再指定导入 DF；SDK / Query 查询真实事实和原始片段；数据服务重启验收通过 |
| GCD 完整协同接力 | Flow→DPLEvolve→CTS/route→GoalEvolve→ECO 真实接力、完整 DRT / RCX、最终事实回流均通过；Goal 无新源码晋升，保留合法基线接力 |
| 接入新 ECO | 使用 ASU-VDA-Lab/TimingECOAgent 的平台 fork，保留作者、原提示、专业操作、评分、回溯和来源 |

完整 Tutorial、新用户安装和论文公平对照未纳入本轮。当前是本机可运行能力和验收脚本，不声称已经交付公开教学产品。

## 真实结果与取舍

### Flow 调参

完整两轮，每轮十二候选，原阶段继承 / GWTW / 预测能力保留；22 次模型请求均成功，报告总用量 **423,200 token**。最终选 iteration 2 / slot 6。

在原 Flow 的 **TT / 固定 CP0=0.458964 ns** 条件下：|TNS| **6077.78→5919.89 ps**，减少约 **2.60%**；功耗 **0.371→0.364 mW**。失败候选、早期首轮过密失败和完整日志保留。

该候选设置 CORE_UTILIZATION=22%，原配置为 65%。候选核心面积 **156.939 µm²**、die **188.184 µm²**；原 ORFS GCD 核心 **61.3089 µm²**、die **79.0143 µm²**。这是显著 footprint 代价，不能只展示标准单元面积，也不能将上述 Flow 原评价与原 ORFS 310ps 最终布线评价混算收益。

### DPLEvolve / ReviewDSE

两者只算一个研究项目。本轮消费 Flow 的真实 `3_4_place_resized` checkpoint，三条原基线和 U3 已独立构建重放的源码候选都完成 EF 原生评价并合法：

| 专业算法 | HPWL (µm) |
|---|---:|
| Diamond | 701.5 |
| negotiation | 698.1 |
| framework | 696.7 |
| 已优化源码候选 | 694.4 |

候选比 framework 少约 **0.33%**，实际运行 1.586s；其结果实际继续 CTS / route。这里复用 U3 的真实专业源码和二进制，没有声称本轮再生成了一轮新 DPL 源码。

### GoalEvolve

输入实际继承 DPL 路由产物，在 EF 中移除 fillers / 旧信号路由以匹配原未布线 DEF 输入语义，不更改原专业优化目标和筛选。

原生真实 GCD baseline：|TNS| **1.95778822899 ns**，动态功耗 **759090647.0795745 pW**、漏电 **825791.1758846603 pW**，DRV=0。原四项结构检查通过；这不等价于 formal 等价证明。

Teacher / 四 Student / AST / EPD 完整一轮、四份真实 C++ 修改、构建、物理评价、反思、Teacher review 和 leaderboard 均正常收尾，停止原因 `campaign_round_limit_reached`。原生保留 baseline，未晋升源码。

收尾发现重复解析 CSV 的执行边界错误：已有 `--csv` 输出被冻结为输入，追加导致虚假 `flow_or_metrics_failed`。桥接已修复，另用新冻结副本执行八次实际重复解析，并用原项目恢复函数和筛选政策核查四份原候选；build / flow / metrics / placement / 原四项结构检查全部通过。四份恢复后的专业 verdict 均为 **refuted**，原因是 **DRV=36–37**；原轮次和错误 EPD 未覆盖。原始 CSV 的 |TNS| 为 **13.629–13.857 ns**，总功耗约 **0.579–0.581 mW**，不能把功耗下降计成合格晋升。恢复结果和原因已导入 DF，并绑定成功物理 producer 和实际日志 hash。

本轮 Goal 报告用量 **12,148,931 token**，其中 **10,650,880 cached input token**；这不等于独立测量的费用或数据增强节省量。原 U4 AES 的已截止预算没有恢复，其历史未完成状态保留。

### 独立 ECO 资格验证

原生运行十五次迭代，最佳为 iteration 9。另行完整默认 detailed_route + RCX，非原项目的一次 DRT 迭代：**DRC=0、placement violations=0、setup TNS=0、worst slack=+0.00548758 ns**。功耗 **1.38819916 mW**、标准单元面积 **45.475 µm²**。

共同条件下原 ORFS 结果重新完整路由：TNS **−0.11987 ns**、worst slack **−0.0415652 ns**、功耗 **1.3730377 mW**、同单元面积。ECO 消除了这次 setup 负裕量，功耗增加约 **1.10%**；这次单实验的取舍不代表平台普遍收益。

Query 对上述两真实运行的 TNS 和 POWER_TOTAL 对比均返回 ANSWERED；修正后的时序快照直接查到 **+5.488e−12 s** 的最差采样 setup path，并有原始 report_checks 证据。hold、完整逻辑等价及其它 signoff 条件需看各自证据，不能由 setup 改善自动推定。

### 完整链路最终结果

最终使用最新 ECO 平台适配源码 `0f8bb06` 的独立冻结副本，真实继承 Goal 合法 baseline；原生九迭代正常停止，输出 ODB / DEF / V / SDC / SPEF 均存在。新增只读探查在真实流程中被调用，原策略没有在这份输入上找到有益的物理 ECO；不把探查或路由漂移当作优化收益。

共同 FF / 310ps / 完整 DRT + RCX 的最终结果如下，输入库和约束固定；时钟在最终时序事实中恢复为 **3.10e−10 s**。

| 指标 | 原 ORFS 共同复测 | 完整协同链路 | 解释 |
|---|---:|---:|---|
| setup TNS (ns) | −0.11987 | −1.8156 | 时序退化，未达时序目标 |
| worst slack (ns) | −0.0415652 | −0.0958744 | 两者均有 setup 负裕量 |
| total power (mW) | 1.3730377 | 0.774380227 | 降低约43.6%，不能掩盖时序和 footprint 代价 |
| cell area (µm²) | 45.475 | 45.7083 | 增加约0.51% |
| core area (µm²) | 61.3089 | 156.939 | 增加约156.0% |
| die area (µm²) | 79.0143 | 188.184 | 增加约138.2% |
| routing DRC / placement violations | 0 / 0 | 0 / 0 | 完整布线与布局检查通过 |

**结论：协作、执行和数据链路已跑通；四项目串联尚未取得满足原时序条件的整体 PPA 改善。** Codex 应保留原 ORFS 为业务基准，将独立 ECO 的时序闭合 / 小幅功耗增加列为明确取舍；完整链路不晋升为“全面更好”的结果。最终 Query 路径查询和同条件 TNS 对比均 ANSWERED，最终产物目录为 `handoffs/collab-final-qualified`。

## 关键问题已定位的修复

1. EF 的共享连接读锁遗漏导致并发 run-detail HTTP500，进而误取消健康构建。补齐 `_attempt_usage` 锁，完整回归 **370 通过 / 1 条件跳过**；更新专属服务后 **120 次并发 GET** 验证通过，旧计算及失败证据保留。
2. ASAP7 原 Flow 时间是 ps，公共边界转换 ns；OpenSTA JSON 为 SI 秒；ORFS 功耗实际为 Watts。错误单位快照保留，但不用于判断。
3. 首轮 Flow 随机样本原来忽略设计约束区间，导致大批过密失败。只约束随机非 baseline 样本；原 baseline65%及优化算法保留。
4. Query 明确快照的对象 / 分析查询保留精确边界；按 run 的指标对比和阶段产物从公共目录读取各类快照，核对所有权，不强行选出唯一事实快照。
5. 最终 SDC 导出原先是 ns 数值、没有单位声明。修成显式 `set_cmd_units -time ps`，真实下游恢复 **310 ps** 的时钟；错误输入 ECO 已取消，错误时序快照排除，最终使用 portable 快照。Tcl ps/ns 两种读者回归均通过。
6. ECO 上游提示声明 `eco_net_sink_report`，公开代码却遗漏实现和过滤入口。补齐只读 OpenDB 连接探查；真实 GCD EF 验证了驱动、负载、方向、master 和缺失 net 报错，不更改优化策略。
7. Goal 重复解析的 `--csv` 是输出，不再误记为冻结输入；对真正输入 log 的变化仍会报错。该修复只影响委派与证据完整性，原专业目标、算法、晋升和结构检查保留。
8. 原 ECO 某些停止路径只留下 best ODB。平台在同一个 EF 会话内确定性导出 DEF / V / SDC，最终再完整 route / RCX。

## 数据底座现在能查什么

执行目录能看到同一 design 的成功、失败、构建、测量和分析 run，以及父运行、状态、资源、日志和文件产物。数据目录能看到 design / revision / run / snapshot，快照摘要、实例 / pin / net、连接关系、指标、位置、采样时序路径及原始来源。

最终协同 STA 快照有 **3,204 个实体 / 6,689 条关系 / 20 条采样路径 / 778 个时序点**。原基准对象快照有 **3,889 个实体**；STA 采样有 **20 条路径 / 526 个时序点**。独立 ECO 修正后 STA 有 **20 条路径 / 514 个点**。这是明确采样范围，不声称已经索引整个设计的全部 timing paths。

初次五个快照重启验收通过；最终包含四份 Goal 恢复事实及协同终态的 **11 个快照**在第二次 DF 重启前后 scope / summary / metrics / objects 逐值一致，digest `828eea9bc798edfaef35fa9cb316d0883aaf25c199a71f9c0a559cb0ec857ad5`。

真实 Codex 驱动的 Query 调查已完成：固定两个输入 scope，五步、32 次领域工具调用、29 条证据，核查时钟、库集合、连接、采样 setup / hold 路径，并给出有证据的差异和后续动作。结果为带明确缺失证据的部分分析，没有把跨设计条件差异硬判为单一因果；记录在 `query-investigation-fixed-launch.json`。

现阶段 Query 给 Codex 提供领域事实、比较、证据片段和诊断操作；源码 / 参数归因要使用对应改动与测量记录。没有凭空证明严格因果，也没有新造通用 Harness 或“评测底座”。数据增强省 token / 时间的公平测量暂缓，不能用总调用 token 充当节省比例。

## 架构和接口

完整模块图、数据流、时序图、实际函数签名、HTTP 路径、数据结构及方案理由见 [OVERNIGHT_GCD_INTERFACES_20261014.md](OVERNIGHT_GCD_INTERFACES_20261014.md)。

HTTP 只用于本机任务和身份控制。大文件通过公共 locator、本机磁盘复制与 hash 校验，远端才用现有分块下载。共同镜像 SHA-256 `8e6ee7aac233da078364649fa8111dac5de33a3589f5445dcffd96f9d6d8dd39`，OpenROAD `27288f5c90265ae5296b2f5a9fa6e8714fa191ad`，ORFS `5105b0a77fe8b3ae107bed67112eb5f83caca5d5`。

## 检查、提交和现场

本轮新增 / 修改文件及职责以各模块独立提交和根仓库检查点为准。包括 Flow 单位 / 首轮约束、Toolkits 单位适配、EF 并发查询、Query 快照 / 多快照对比、两个 Code 的 SDK 输入上下文、ECO 可选 Codex / EF 会话 / FF 库 / 最终导出 / 只读探查，以及 root 的准备、运行、资格验证与数据验收助手。

运行数据、凭据、镜像和环境未提交。原用户 **26 份文件**及 DF / DI 未提交修改保持原状，hash 验证完成。发布到 `CODA-Team/ChipEvolve` 的夜间分支和 `modules/*`；不修改旧生产服务及原 U4 AES 数据。

权威现场：`var/overnight/gcd-20261014/runtime.json`、`progress.json`、`tasks/`、`agents/`、`handoffs/`。源码固定版本见根 `SOURCE_MANIFEST.json`。缺失的上游 AES LFS 对象返回404，未声称复现其官方 AES benchmark；本轮使用真实本机 GCD。

## 本机复查

使用 `runtime.json` 指定的 installed SDK 解释器运行 `admin/overnight_data.py inspect --state var/overnight/gcd-20261014 --key eco-smoke-portable`。使用 Query CLI 指定 `gcd-20261014-eco-smoke-portable-timing` 能查询原始采样路径及证据。不要用裸宿主 OpenROAD 或 sibling PYTHONPATH 替代共同环境。

工程门禁：EF 370通过 / 1条件跳过；Flow57、Toolkits57、DPLEvolve18、Query160、GoalEvolve418项回归通过；ECO4项边界回归通过，Root7项验收助手测试通过。本轮修改文件的静态、类型 / 格式、逐文件差异、模块边界与真实实验核查通过；Query 三条依赖契约全部保持。Goal 一次 localhost 测试受宿主代理影响，设置既有 NO_PROXY 后全418项通过，失败日志保留。

最终公开 API 验收回执保存 **335 个运行**（298成功 / 31失败 / 6取消）的目录和每个运行资源统计、各阶段输入 / 来源、最终实体和时序计数、持久性及26份用户文件 hash 核查；原生会话与 EDA 任务全部终态。原错误单位数据、取消的计算、CSV 后处理失败和上游 LFS 缺失均保留，不能作为改善证据。

新增 Root 文件职责：`overnight_runtime.py` 管公开任务与回执，`overnight_data.py` 导出 / 导入 / SDK 检查，`overnight_dpl.py` 处理真实布局接力，`overnight_goal.py` 准备原生 Goal 轮次，`prepare_overnight_eco.py` 冻结输入和源 / 提示 / Tcl 身份，`overnight_finish.py` 完整 route / RCX 与明确单位的 SDC 导出；对应测试覆盖失败留证、来源变化和跨单位交接。接口图和本报告说明真实数据流与边界，PROJECT / ARCHITECTURE / TASKS / SOURCE_MANIFEST 固定最终检查点。下轮应优先按实际测量优化失败案例和候选选择，再选择更大设计验证；扩展设计规模不自动等价于扩大本轮已完成声明。

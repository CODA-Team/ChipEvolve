# P3 / L1 本机完整 Flow 验收

更新：2026-10-11。完整真实工程验收已通过；最终业务确认待老板。本报告不宣称两个 Code 项目或整个平台已经交付。完整结论见 `var/flow-agent/p3-platform-campaign-20261011-retry3/p3-acceptance.json`。

## 老板得到的功能

- 真实 AES 两轮、每轮三个候选的专业调参，沿用原生 A2 的搜索、淘汰、继承和实际 OpenROAD 物理流程。
- 物理运行和评价统一交给执行底座，实验身份、输入、资源、日志及原始产物有登记。
- 真实模型和计算中断后可复用；四个预定的实际中断窗口均已执行并恢复，原 run、产物和模型响应保留，没有重复运行已完成的任务或重新调用已保存的模型决策。
- 真实评价自动进入数据底座，通过安装的公共 SDK 核对数值、单位、评价条件和原始来源。

## 当前证据

运行目录：`var/flow-agent/p3-platform-campaign-20261011-retry3`。Flow 源码固定为 `a90bd07e304e2572fbd3e201809d93d6e50cbe1c`，campaign 为 `20261011_053913_583816_seed42`。

两轮六个候选全部完成；18 项物理阶段、12 项评价、12 项导出共 42 个 run 全部成功。源码与安装环境未变。实验于北京时间 13:39:11 开始，14:22:29 完成，包含四次主动中断及恢复。最终 176 项工程核查通过，18 项实际参数消费匹配，12 个评价快照通过 SDK 来源检查。

固定 CP0 为 0.792 ns，功耗上限为 0.400 W。signed TNS 越接近零越好：

| 轮次 / 候选 | TNS（ns） | 功耗（W） | 本次结论 |
|---|---:|---:|---|
| 第一轮 / 1 | -4.36 | 0.400 | 基准 |
| 第一轮 / 2 | -7.07 | 0.398 | 可行，时序更差 |
| 第一轮 / 3 | -7.22 | 0.399 | 可行，时序更差 |
| 第二轮 / 1 | -4.11 | 0.400 | 最优可行，\|TNS\| 改善约 5.73% |
| 第二轮 / 2 | -4.41 | 0.402 | 功耗超限，不计可行收益 |
| 第二轮 / 3 | -4.43 | 0.400 | 可行，时序未改善 |

本次成功 campaign 内部模型共 17 次调用，全部成功；账本记录 305,632 token，其中输入 301,836、输出 3,796，输入缓存 35,584。这个数字不包括主 Codex 对话、前期失败尝试及调试成本，不作为平台端到端成本对照。

跨轮七次真实模型响应已逐项审阅并保存来源。第二轮的 LLM-origin 入选参数等于基准参数，是重复运行；另一个探索候选来自数值采样。两项第二轮阶段模型选择分别为 CTS kmeans/0/0 和 routing hybrid/0.55/0.3，日志与真实模型配置一致，但入选参数均来自 exploit/lhs/lhs，保留原始来源，不改标成模型提案。跨轮原生 GP 在历史不足时使用 dummy model，ReAct GPR 分支跳过；第二轮 CTS 候选 GP 还记录了数值拟合错误并转用 simpler model。保留这些实际回退，本次不能证明相关分支的预测质量。

完整运行、单次优化观测和预测质量分别报告。平台相对 ORFS 的公平 PPA 收益，以及数据能力节省多少 token/时间，留到 L8 的固定条件对照。

| 证据文件（相对于上述运行目录） | 证明什么 |
|---|---|
| p3-acceptance.json | 完整收尾核查与工程通过，业务确认待老板。 |
| receipt.json / interruption-*-before.json / final-execution.json | 五次 Controller 启动、四次实际中断，以及原请求/run/产物/模型的保留。 |
| model-decision-review.json / decision-review-evidence/ | 实际模型决策、CSV、配置/约束、参数来源和数值回退。 |
| sdk-feedback/ | 12 项评价的 SDK 指标、条件、metadata artifact/hash。 |
| sdk-final-verification-retry1/receipt.json | 原 EF/DF 状态以 API-only 重开，数据来源验证通过，42 个 run 身份/状态不变且无重跑。 |
| local-transfer-check/receipt.json | 真实大物理包的本机交接速度及 hash。 |

收尾只读核查第一次使用了超出公共分页范围的 limit=1000，改为既有支持的 500 后通过；保留 `sdk-final-verification/receipt.json`。SDK 回执尚未齐全时的初次审计保留为 `p3-acceptance-initial-sdk-pending.json`；没有降低全量来源要求，也没有重跑 EDA。

## 本机 HTTP 与文件读写

HTTP 是进程间发消息的协议，不等于互联网下载。当前专有服务监听 `127.0.0.1`，任务、状态、摘要和定位信息留在本机通信。

大型物理产物通过现有公共 `KernelClient.materialize_artifact(run_id, artifact_id, destination)` 取得执行底座核准的本机路径，然后复制并校验 SHA256。后续阶段交付已登记的 artifact_id，由执行底座装入任务目录；专业 Agent 不自行读取执行底座私有数据库。远程部署才使用该接口已有的分块下载。

真实 17,579,571 字节布局包的定位信息约 723 字节，定位耗时约 0.007 秒，定位、复制及校验合计约 0.026 秒。条件为已有文件缓存；这是实际交接检查，不是稳定磁盘吞吐测试。证据为本次 `local-transfer-check/receipt.json`。4 MiB 是整包响应接口的应用限制，不是 HTTP 协议的文件大小限制，也不限制当前本机大包取回路径。

## 必要修复与文件职责

| 文件 | 职责与修改原因 |
|---|---|
| flow-agent/flow/platform_execution.py | 物理阶段包改用现有 materialize 接口，解决真实 17.6–18.0 MB 包超过整包响应上限的问题。 |
| flow-agent/flow/test/test_platform_execution.py | 新增超过 4 MiB 的真实 ZIP 结构回归，验证物理包交接；评价日志路径保持原有行为。 |
| admin/run_platform_campaign.py | 修正本次独立实验的 8 核额度及 GNU timeout 子进程组停止，管理全部专有 Controller publisher，保留 EF 独立 worker。 |
| admin/test_platform_campaign_budget.py | 真实 API 验证 8 核任务受理、超额拒绝。 |
| admin/test_platform_campaign_control.py | 真实 timeout/锁和独立 worker 验证中断边界。 |
| admin/accept_platform_campaign.py | 完整实验收尾审计：实际恢复、任务/产物/模型身份、正常结束、两轮 canonical、真实参数消费和模型决策证据。 |
| admin/test_platform_campaign_acceptance.py | 验证原请求/产物不可替换，且工具日志必须匹配配置参数。 |
| admin/query_campaign_feedback.py | 通过安装的 Data Interface SDK 核对真实评价值、单位、条件和原始 metadata 字节。 |
| admin/test_campaign_feedback_query.py | 不一致的数值、单位、评价条件和来源均拒绝。 |
| ARCHITECTURE.md / TASKS.md / admin/STATUS.md / admin/LOCAL_EXECUTION_PLAN_20261011.md | 保留目标边界，记录实际状态、失败和后续施工计划。 |
| admin/P3_SLICE_REPORT_20261011.md | 本轮老板汇报、证据与验证交接。 |

前三次失败尝试完整保留：首次 CPU 受理预算不够；retry1 中断脚本漏停 timeout publisher；retry2 大包取回被拒。每次修复后使用新的冻结运行副本，不编辑正在执行的源码。上述资源/中断修复已有根目录 Git 检查点；大包修复已有独立 Flow 提交 `a90bd07`。

## 工程门禁与数据流

Flow 大包修复后的既有及新增检查共 48 项通过。新的收尾脚本 lint、格式、类型、编译检查通过；恢复/资源/进程边界单元检查 9 项通过，SDK 来源检查 4 项通过。原始记录见 `var/flow-agent/p3-campaign-audit-checks-20261011`，最终脚本 hash 和检查记录见 `var/flow-agent/p3-campaign-audit-final-checks-20261011/receipt.json`。Flow 在 48 项检查后没有新增源码变化，收尾复用该基线的回归记录。

数据流：A2 的候选/阶段 → 公共 EF TaskSpec → Toolkits/OpenROAD → 登记原始产物和真实 CP0 评价 → Toolkits metadata 导出 → DF 指定产物导入 → DI SDK/Query 提供事实与来源 → Codex 判断。

架构检查：没有修改公共接口或 EF/DF/DI/Query/Toolkits 源码，没有跨项目 PYTHONPATH/sys.path 接线，没有通过私有数据库实现业务；运行副本、原有用户修改和旧服务保留。参数消费审计只读取登记的原始日志，不绕过 EF 启动 EDA。

## 尚未交付

DPLEvolve/ReviewDSE 和 GoalEvolve 尚未本机原生运行或接入平台。按设计统一查看全部实验/产物/原因、真正的 Query→Flow/Code 业务接收器、统一 Code 执行和数据入口、三项目协同以及本机收益对照，仍属于 L2–L8。ECO、教学、新用户安装和论文交付暂缓。

## 三句话交接

1. 本切片修正本机完整物理产物交接和真实中断验收边界，并补齐对应检查、完整审计与状态文档；文件职责见上表。
2. 原生 A2 负责专业搜索，EF 执行并登记原始产物，Toolkits/DF/DI 提供统一评价事实，Codex 负责判断和下一步。
3. 改大文件取回看 platform_execution，改续跑看 platform_campaign/platform_model，改数据回流看 platform_feedback；后续 Code 接入和设计视图按独立切片施工。

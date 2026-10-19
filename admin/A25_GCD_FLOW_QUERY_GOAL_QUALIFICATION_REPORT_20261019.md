# A25：真实 GCD Flow→Query→Goal 的可行交付

完整原参数域 Flow2×50 的第 2-37 分支经过 Query 诊断，实际交给原 Goal 一轮四 Student：输入 ODB/SDC/网表和上下文身份均绑定，Teacher 提示确实包含源面积 44.8918µm²、原上限 42.6757µm²及至少削减 4.9365% 的诊断。源面积超限在现代来源中已存在，不能把来源与调参差异混作 Flow 或团队收益。

## 最终业务结果

四个原生候选都交付了共同 FF/310ps 完整布线/RCX 与 SDK 事实，其中两份满足原约束，两份因 setup TNS 被拒绝。

| 分支 | 功耗 mW | 单元面积 µm² | setup 余量 ps | 原约束 |
|---|---:|---:|---:|---|
| 原 ORFS 控制 | 1.373553765 | 42.6757 | 见原控制 | 基准 |
| 实际 Flow2-37 交接源 | 0.890911557 | 44.8918 | 12.289 | 面积超限 |
| Goal Student01 | 0.755599816 | 39.2348 | 5.31003 | 通过 |
| Goal Student02 | 0.715648639 | 39.1181 | 0.0834055 | 通过 |
| Goal Student03 | 0.768538506 | 38.7974 | −70.4802 | setup TNS 不通过 |
| Goal Student04 | 0.766251818 | 38.9869 | −92.9781 | setup TNS 不通过 |

Student01/02 分别通过全部 18 输出 ABC-PDR、独立完整 DRT/RCX 七 PPA 同值、原十项约束和额外 fanout=0、实际注册原件及公共 SDK 核验。独立布线从原注册 Goal native checkpoint 启动，父 run 与 common measurement 各自角色分开；没有重复模型搜索。

Codex 按原约束内优先降低功耗的目标，在本轮独立 GCD runtime 保留 Student02，Student01 作为时序余量更大的已验证备选保留。原 Teacher 晋升 Student01 的决定和原 parent/评分不改写。Student02 相对原 ORFS 功耗 −47.8980%、单元面积 −8.3364%，相对实际 Flow 交接源功耗 −19.6723%、单元面积 −12.8614%。时序余量明显减少，不能宣称更高频率或无代价改善。

**这证明本次完整 Flow→Query→Goal 可以得到有证据的合法 PPA 分支，不是同总预算团队优于最强单项的正式证明。** 原来源差异、完整 Flow 的失败成本及 Code 原生轮次成本必须一起报告；这些开发样本不能当未见设计。

## 修复的交付接点

原生四 Student、Teacher review 已正常完成，但 EPD 检索默认将轨迹写到 `round_000/teacher_epd_retrieval_trace.jsonl`，候选导出器错误要求它具有 `round.json`，导致交付失败。Goal 候选修复 `7b03c33` 只区分“零轮无 Student 的检索轨迹”与实际优化轮次，保留原日志；未完成的真正轮次/Student 仍拒绝导出。没有删轨迹、重跑演化或改专业算法。

- 两个文件：`goalevolve/platform/candidate_evidence.py` 四行适配；`tests/unit/test_candidate_evidence.py` 三项回归。
- 旧用例 1 失败/6 通过，新用例 7 通过；完整 Goal 回归 437 通过、3 跳过、24 subtests 通过，lint/格式/类型/差异通过。首轮回归的 localhost HTTP502 是测试代理环境问题，原日志保留，r2 仅显式绕过本机代理。
- 原 GCD native 源码 `3f35d82`、request/profile/模型用量及原 EPD 轨迹逐 SHA 保持。后处理只通过新配置将既有 `professional.goal.source` 指向修复后的只读导出器，native 执行身份没有改写。修复发布到独立模块分支，主 Goal 合入须等待被冻结消费者收尾。
- 第一次恢复驱动只枚举 `materialized-result.json`，实际候选清单绑定 `result.json`；已独立沿真实 inventory 将四份结果逐一核查。初步单行摘要不作为全候选验收。第一次独立物理审计误把 common run 当 native 输入父 run，失败保留；r2 按实际父产物、消费字节和完整阶段重新核验，没有重跑 EDA。

证据位于 `var/business/a25-goal-epd-trace-export-20261019/`：两份独立验证审计、四候选 SDK/PPA 审计、`student02-adoption.json`、原始状态 SHA 和交付恢复回执。26 份用户文件保持，跨项目只用已装 wheel/公开 EF/SDK，没有路径注入。

## 成本与接下来的工作

原生本轮 11 次专业 Codex 调用记录输入 6,833,091、输出 121,748，共 6,954,839 token；5,764,608 cached input 是输入子集。它不是后台 API 请求计数，也不包括主协调 Codex。r41 新记本轮 80 项全部终态 EF 任务，均属 GCD，采样 CPU 5,312.75 秒；原 Flow/Query 成本在旧账中，不重复相加。主推理、服务导入、测试和源码复制等未观测成本不填零。

唯一新主管 `3871969` 已开始原定五份 JPEG 匹配物理控制；之后仍为原 ECO8轮、显式 measured-mode Goal1×4、健康完整 JPEG2×50。未来 Goal 仅重绑定已修复导出器的清洁源码/新环境，原 case key、算法、目标、候选数和预算不变。旧失败主管不会重启。

数据服务新健康读取已持续通过，GCD 交付后的新快照可查询；仍继续记录 JPEG 大事实导入窗口，不把短读数或本次交付当作全部稳定性已解决。A25 未冻结，公平 A26/A27 与最终 A28 核查尚未完成。

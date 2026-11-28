# 四项目与历史数据成果核查

核查日期：2026-10-08。核查方式：阅读用户两份 PDF、正式源码、迁移清单、历史工作树和原始实验汇总；重新计算来源哈希和汇总统计。本次没有重跑 EDA 或模型 benchmark，也没有切换旧服务或迁移大数据库。

## 1. 管理结论

Data Foundation 有可继承的实质基础。历史成果保留在正式数据项目中，并有可追查的真实大设计实验记录。当前最需要做的是完成独立项目后的能力验收、修正工具适配边界、把主 Query Agent 接到已有丰富数据上。

Execution Foundation 已移除账户/会话、旧控制台、应用代理和 Plan executor 的运行逻辑；“彻底收尾”仍未完成。商业适配、历史准入资料和部分说明仍混在执行项目中，需逐项判断归属。不能根据 identity/session 等单词删除产物身份、worker 身份或操作系统进程会话。

主 Query Agent 保留了有价值的类型、数据端口、作用域和证据规则，但没有成熟的自适应诊断引擎。历史平台里的另一套 Query 实现不应算作主项目已经完成的功能。

## 2. Data Foundation 是否从零开始

对照对象：`/home/wjyuan/projects/eda-ai-final-window-20261004/apps/data_foundation/src/openroad_app_data_foundation`。

| 文件级核查 | 结果 |
|---|---:|
| 历史 Python 模块 | 47 |
| 当前 Python 模块 | 48 |
| 哈希完全一致 | 37 |
| 保留路径、内容有修改 | 10 |
| 历史有、当前缺失 | 0 |
| 新增 | `catalog.py` |

10 个修改模块：`__init__.py`、`artifacts.py`、`bundle.py`、`engineering.py`、`envelope.py`、`evidence.py`、`metadata.py`、`path_endpoints.py`、`queries.py`、`server.py`。保留模块不等于证明行为无变化；后续必须以原生 gold 和历史任务验证。

迁移已保留：快照入库与 SQLite 索引、实体/连接关系、时序路径与有序节点、时序对象关联、路径增量、pin/net 排名、几何统计、拥塞与全局布线、实例功耗分析、原始来源和有界取回。代表性代码包括 `repository.py`、`resolved_timing.py`、`engineering.py`、`pin_net_ranking.py`、`congestion.py`、`global_routing.py`、`instance_power.py`。

原 SDK 中设计目录聚合、对象名称匹配、指标归属已归 Data Foundation。当前 Data Interface 的源码主要是 SDK 传输和工具定义，未引入数据库或新服务。

尚未完成的边界：Data Foundation 的 `native_queries.py`、`timing_queries.py`、`analysis_setup.py`、`instance_power.py` 等仍包含 OpenROAD 专用命令和执行任务构造。`server.py` 的部分 GET 查询会触发新分析任务。建议保留现有能力并用验收保护，逐步把工具命令/加载/导出迁入 Toolkits；查询和创建分析任务应有明确不同的动作语义。不能为了“分层漂亮”先删功能。

## 3. 历史论文数字是否有原始记录

文档二对应的七轮结果位于 `/home/wjyuan/projects/eda-ai-formal-20261002/results/next_models/*netgeometry-formal01/summary.json`。重新按 design/question 配对，并只将双方 usage 完整的 pair 纳入成本。

| 原始模型名 | Interface/Raw 正确题数 | 完整成本对 | Token 减少 | 在线时间减少 |
|---|---:|---:|---:|---:|
| gpt-5.6-luna | 71/70 | 72 | 71.609% | 64.253% |
| gpt-5.6-terra | 71/70 | 71 | 32.704% | 52.732% |
| gpt-5.6-sol | 72/72 | 72 | 41.685% | 56.847% |
| gpt-6-sol | 72/72 | 71 | 6.916% | 44.520% |
| gemini-3.1-pro-preview | 72/71 | 71 | 64.140% | 68.533% |
| deepseek-flash | 71/68 | 70 | 81.725% | 73.982% |
| deepseek-v4-pro | 70/69 | 69 | 82.159% | 78.555% |

合计 1,008 episodes、504 对任务、496 对完整成本记录。主要数字与 PDF 一致。此次计数使用保存的 `passed` 字段，尚未独立重判每个答案、gold 或证据引用，因此属于汇总复核。

文档二的 Ariane 消融也有记录，在 `results/final_ariane_ablations04`：

| 条件 | 正确 | Tokens | 在线秒数 | 工具调用 |
|---|---:|---:|---:|---:|
| 完整能力 | 24/24 | 868,725 | 812.185 | 42 |
| 扩大输出 | 24/24 | 1,145,847 | 853.652 | 55 |
| 去关联/组合能力 | 24/24 | 1,872,483 | 1,320.101 | 139 |
| 去按需原生分析 | 22/24 | 3,154,293 | 1,344.074 | 122 |

这些历史实验支持当时整套“数据后端＋查询入口＋工具补充”的作用。它们没有分别证明四个独立仓库的贡献，没有证明主 Query Agent 更擅长根因推理，也没有计入准备成本、冷启动或强持久原生会话基线。不能把历史 Interface 条件的收益归给今天的薄 SDK。

## 4. Execution Foundation 清理核查

运行代码中，`gateway` 只组合本地 HTTP 与 worker；`build_kernel()` 明确不创建 identity 数据库或应用注册表。当前测试包含旧账号/代理入口返回 404 的断言。

应保留的执行职责：任务/尝试状态、幂等提交、输入 staging、取消/超时/进程树清理、资源预算、产物哈希、日志、来源及 evaluator 隔离。这些是可追溯实验所需能力。

仍需后续处理：

- `plugins/cadence-innovus` 与商业工具相关测试应跟随工具适配归入 Toolkits，当前仅做 OpenROAD/ORFS 的发行入口不应宣称商业工具已验收。
- `admissions` 同时保留商业工具和外部能力资料；有些不存在同仓库 manifest，但可能对应外部插件。按部署消费者核查后归档，不能仅据“本地没目录”删除。
- 仓库采用 OpenROAD 历史包名；这些名称不表示运行内核仍包含 EDA 算法，公开发行时需要明确包装说明。
- 两份 Research Toolkit 示例 README 原本指向已删除的 Plan executor 验收。本次已改为实际存在的插件/HTTP 集成检查，并明确其没有验收研究 Toolkit 的 script/patch 能力。

既有独立验证记录为 EF 384 passed/1 skipped、DF 342 passed、DI 10 passed、QA 87 passed，总计 823 passed/1 skipped，见 `admin/ACCEPTANCE_REPORT.md`。这是之前实际运行的检查，本次没有重复计作新测试。

## 5. 主 Query Agent 的真实缺口

真实 Data Foundation provider 已接实例/net/pin、WNS/TNS、时序路径和实验作用域。`get_connections/get_fanout/get_location/get_instances_in_region` 仍明确抛 MissingDataError。数据后端有部分对应能力，不代表主 Agent 已接通。

现有 LLM 管线更接近待完成的接点：`LLMQueryPlanner.plan()` 丢弃原始 request，仅把 intent 交给模型；`prompt_version` 字段并不等于加载了相应 prompt 文件；具体 LLM adapter 目前只有 fake。`DiagnosisProvider` 的 fixture 展示类型契约，不能生成真实新根因。

下一轮应把证据、假设、补分析和诊断工作流真正接起来，并以真实问题验收，避免靠增加 prompts 文件或更多 unavailable 分支宣称能力提升。

## 6. 可复核文件

标准库脚本：[reproduce_audit.py](reproduce_audit.py)。输出：[code-and-paper-audit.json](../../var/research/20261008/code-and-paper-audit.json)，包含四项目 commit、模块哈希对照、原始汇总文件 sha256、配对统计和限制。

```bash
python3 admin/research/reproduce_audit.py \
  --historical-code /home/wjyuan/projects/eda-ai-final-window-20261004 \
  --historical-results /home/wjyuan/projects/eda-ai-formal-20261002/results \
  --output var/research/20261008/code-and-paper-audit.json
```

下一阶段的科研地图、职责设计和验收路线见 [Query Agent 研究与设计](QUERY_AGENT_RESEARCH_AND_PLAN_20261008.md)。

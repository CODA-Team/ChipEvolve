# A55：找回已完成的 Ariane 修正供电来源

2026-10-25 A60补充来源语义：原benchmark README明确SRAM为FakeRAM2.0，提供LEF/Lib抽象模型；默认ORFS的fakeram.*未匹配该名称。新私有声明的原生导出/实际136实例核验已通过，宏内部几何仍为抽象。下文原缺GDS错误、原failed/PPA及未采用保持；当前研究PPA不再以寻找真实SRAM制造版图为前置。见 [A60](A60_ASAP7_FAKERAM_STREAMOUT_20261025.md)。

接续根 `b916286`。本轮修正一项会导致重复施工的诊断遗漏：A52 验证的是旧失败来源和事后重建 PDN；另一条已完成的、在布线前应用 PDN 修正的来源没有纳入 A54 当前清单。**修正来源的原 ORFS 最终 PSM 已通过 VDD/VSS 连通检查，整场失败发生在之后的 SRAM GDS 合并。** 不应继续将此分支的阻断记成“供电修正尚无最终报告证据”。

本轮没有新 EDA、模型、优化、布线或证明计算。仅通过公共 EF 获取原件并复核，再用一个既有 ORFS metadata 导出任务补充 DF 阶段事实。没有产品源码、模块版本、公共接口、服务或资源容量变更。

## 三条来源必须分清

| 来源 | 实际句柄 | 本轮核查结果 |
|---|---|---|
| 旧原始 PDN 完整来源 | `run-d05441469fa744d2856ec6c24de5aa12` | 原 `6_report` 的 VDD 连通失败；A52 对它的负诊断保持有效 |
| 早期修正配置的首次申请 | `run-2c6a562e2c6c41ea9a63f564c59409ab` | 取消、无产物；不能代表所有修正来源均未执行 |
| 相同修正输入、28 GiB 申请的完整来源 | `run-9efb2a4da95144d299b49b1d7d4a9abb` | 实际走完 DRT/RCX/原生 final_report；VDD/VSS 连通通过，随后因缺少 `sram_asap7_16x256_1rw` 的 GDS/OAS cell 失败 |

第三项在 10 月 22 日本机约 05:20 已结束，结果后来经 `run-3792ba19f8124d4e845399234640011a` 共同测量，并形成了可查的三类快照。本轮没有恢复或重启旧进程，也没有重测设计。

## 用什么证明

- 公共 EF 原件取回 12 份日志、请求/结果及阶段 JSON，逐件 SHA 与登记记录相同。
- 比较两来源公开 attempt 的实际输入，原网表、宏布局 DEF、SDC、LEF 和库均保持；修正来源实际输入含 `compatible-pdn.tcl`，其 SHA 与既有相位修正一致，`design.mk` 显式设置 `PDN_TCL`。不是在旧信号布线完成后平移供电网。
- 修正来源 `extractor.log` 第 **4925** 行进入 `final_report`，第 **5178/5190** 行分别记录 VDD/VSS `PSM-0040 All shapes ... connected`；第 **5232** 行记录 `6_report` 完成，第 **5255** 行才出现缺失 SRAM GDS/OAS cell，第 **5258** 行为 `do-gds-merged` 失败。
- 同来源 `6_report.json` 含 VDD/VSS IR 指标、136 个宏实例和零 final_report 错误；`5_2_route.json` 的 DRC 为零。旧来源则在 final_report 中明确记录 `PSM-0069`。
- 共同测量的 physical_run_id 指回第三项，SDC/21 库身份与该次实际输入一致，实际 SPEF SHA 与原登记文件相同。原 result 同时明确 `original_flow_status=failed`、GDS 缺失及 adopted=false，本轮不改写它。

此结论的精确范围是**修正来源的原 ORFS 最终 PSM 报告通过**，不是另行运行任意参数的 `check_power_grid`，也不是整场流程、完整 GDS、功能证明或 PPA 业务资格通过。A52 已证明的“旧已布线结果事后重建 PDN”失败仍然成立。

## 当前真正的剩余问题

| 指标/交付 | 已有共同测量或原始状态 |
|---|---:|
| 测量条件 | ASAP7 / FF / 0.9 ns，原映射网表与宏布局 |
| 功耗 | 641.95156097 mW |
| 单元面积 | 43653.4 µm² |
| setup WS / WNS | −288.838 ps |
| setup TNS | −127.168 ns |
| hold WS / TNS | +9.73535 ps / 0 ns |
| slew / cap / fanout 违反 | 444 / 0 / 0 |
| 原生详细布线 DRC | 0 |
| 原 ORFS 最终 VDD/VSS PSM | 通过 / 通过 |
| GDS 合并 | 缺少实际 SRAM GDS/OAS cell；失败 |
| 功能证明 / 采用 / 成功优化重复 | 未据本轮建立 |

这些是既有来源事实，不是本轮新增 PPA 或优化收益。GDS 资料缺失与时序/电气问题应分开：已有 ODB、SPEF、网表和库可以用于后续 PPA 修复；现有 GDS 不完整，不能标成完整交付。不要为重复确认已经通过的供电阶段再重跑整场，也不能因 GDS 缺失抹去已完成的物理与测量事实。

## 数据底座现在可以查到什么

新 EF metadata 导出 `run-9b460d04390c406d88f4a119f1014d20` 成功，subject 仍是**原失败物理任务** `run-9efb…`，原任务终态保持 failed。新 snapshot：

`a55-run-9efb2a4da95144d299b49b1d7d4a9abb-native-final-stage-audit`

六项无量纲阶段标志/计数经现有 DI `get_metrics(include_raw=True)` 逐值核验：VDD connected=1、VSS connected=1、final_report completed=1、original flow succeeded=0、GDS complete=0、route DRC=0。它们作为原始事实保留，不冒充 canonical PPA。阶段记录同时说明 GDS 缺失原因，附原日志/JSON 的 EF artifact ID、SHA 与原生行号。

DF 证据引用指向实际导出 run 的 metadata artifact，而非错指物理 subject。公开 source excerpt 的原始字节与 metadata SHA 相符；metadata 继续引用已逐件校验的原生来源。原 `run-3792…` 的精确快照/修订 Query 查询仍返回 WNS **−0.288838 ns**，引用可取回，未将供电通过误写成时序闭合。

## code-check、改动与接续

运行证据：`var/business/a55-ariane-corrected-pdn-evidence-20261025/`，主要文件为 `corrected-pdn-source-audit.json`、`stage-fact-publication-receipt.json`、`DF-native-final-stage-facts.json`、原件索引与 Query 输出。两个私有核查/发布脚本通过 Ruff、格式和 Pyright；首次静态检查发现把通用配置 reader 的字典类型用于列表索引，改用 JSON 列表读取后通过。试用不存在的 SDK/HTTP sources 列表入口失败后，改用已返回证据的公开 excerpt 地址；没有为核查新增接口或修改产品。

产品与专业源码未变，复用 A53/A54 同源码检查点的现有回归；本轮验证直接覆盖两条真实相反来源、已取消分支、原件身份、数据交付、引用与仍为负的 WNS。26 个用户保护文件、历史 result 和待用配置保持。提交文件只包括本报告、A52/A54 的明确更正、ARCHITECTURE 阶段边界说明及 TASKS/STATUS 续接索引，运行材料不发布。

下一步不再给该修正来源重复打 PDN 补丁：查其已完成 ECO/时序修复分支的实际动作、输入和失败，针对 444 slew 与 setup 债选择已有原生修复策略；GDS 缺失单列为资料交付问题。Ibex/Nangate45 完整证明、Ariane/Nangate45 电气及最终资格、500 ps 协作和八组双次目标仍未闭合，长搜索继续暂停。

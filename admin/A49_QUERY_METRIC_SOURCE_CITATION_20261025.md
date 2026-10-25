# A49：指标引用指向真实登记原件

接续A48根 `abfef57`、Query `aad2520`。本切片只修改Query的原件目录与引用传递，无新EDA、模型、服务或公共协议。

## 诊断更正与实际缺陷

A48新摘要最初漏单位，补单位后仍漏corner。Query的complete判断同时要求原件/单位/corner，现有通用reason却只写metric source artifact is missing。**最初把NEEDS_MORE_DATA直接归因于原件run混用，判断过早**。补入原脚本实际ns及实际库typical声明后，旧Query已能回答TNS0，未放宽完整性规则；历史不完整快照保留。

随后核查这个已回答的引用，确认真实缺陷：指标的subject为物理run，原JSON属于独立导出run，但引用被拼成 `execution://runs/<subject>/artifacts/<export-artifact>`。公共EF实际核对证明，该artifact不属于subject，却明确属于导出run；旧链接无法代表其真实归属。

## 改动文件及边界

| 文件 | 职责 |
|---|---|
| `query-agent/src/query_agent/adapters/data_foundation/experiments.py` | 未指定物理阶段时也保留DF索引的source引用，与既有EF原件目录合并；无索引数据的404维持原EF目录；其他错误不吞掉 |
| `query-agent/src/query_agent/application/collection.py` | 指标引用优先采用已有ArtifactRef.locator；不再把DF原件套到subject的EF路径，原Scope保持 |
| `query-agent/tests/contract/test_data_foundation_adapter.py` | 新增无stage原件、实际引用/精确scope及无DF退回原目录回归 |

原DF/DI公共端点、Query ports/domain模型、complete条件、snapshot/revision校验、数值、单位、corner、排序和Codex决策权均不变。没有为诊断重造framework或另开harness。

## 门禁及实际安装包验证

修复前2个新用例复现错误；修复后28相关/182Query全回归、712根回归通过。Query全项目Ruff/format/Pyright通过，import-linter3约束全保持；pip check通过。类型检查最初指出新夹具的固定三元素tuple被替换成单元素，已只修夹具，失败日志保留。

独立wheel：`563047251da928c998305d90aab6a8cfc291a42e9b0acd9eb334c089b02aa36a`；安装于 `var/business/a49-query-metric-source-citation-20261025/query-runtime`。两份产品源文件、wheel与实际安装文件字节相等。

四项真实只读检查：

- 新Ariane GRT/TNS0回答成功；引用通过DF的snapshot/source端点实际取回，原件SHA/完整文本SHA与回答provenance完全一致。指标subject/snapshot/revision及数值保持。
- 同run/snapshot、错误revision返回不足，无证据。
- 缺corner的旧诊断返回不足，不冒充完整指标。
- 历史GCD/ASAP7的WNS查询仍成功；新原件链接实际取回。

本次新增EDA0、模型0。26保护文件保持，EF活跃队列收尾为空，原服务/容量未改。旧A33运行环境和历史配置不热切；下一批八份私有配置在同目录 `configs/` 显式绑定已验证A49解释器，原专业templates保持。它们不等于自动放行长搜索。

## 可续接状态

Query模块已提交/发布 `01abe98` 到原隔离模块分支，根仅更新该gitlink及manifest。原集成分支候选、DF/DI用户WIP不动。A48报告同步更正诊断原因；TASKS/STATUS/ARCHITECTURE记录当前边界。

证据：`var/business/a49-query-metric-source-citation-20261025/` 的测试/静态/依赖日志、installed-verification、真实source响应、final-code-check与future-query-bindings。若需调整指标原件如何呈现，改上述适配器目录与collection引用传递，不改DF存储或指标语义。

Ariane原14动作兼容已通过，但剩余电气违反及最终DRT/RCX仍待后续业务验证；Ibex/Nangate45完整证明、八组双次合格结果和新500ps完整专业搜索仍未完成。长搜索继续暂停。Query对不完整指标的通用reason仍不够精确，已记录；它不影响本次完整事实的引用修复。

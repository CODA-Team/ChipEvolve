# A33：具体诊断 → 修复阻断 → 短验证 → 代码检查

2026-10-25。本切片只修复 Query 普通指标查询丢失精确快照身份的问题。未启动 EDA、优化搜索或模型调用，未重启服务、变更生产容量或数据库，未改历史实验。

## 问题与修复

此前按 run 查询 WNS 可以回答，但同时指定正确 snapshot/revision，反而返回 NEEDS_MORE_DATA。定位确认：DF/DI 已返回完整身份；`DataExperimentProvider` 转为内部 `MetricObservation` 时只保留 design/run/stage，证据转换后也不再具有 snapshot/revision，严格匹配因此拒绝真实指标。

修复继续使用原来的数据链：DF → 已安装 DI SDK → Query 适配器 → 内部指标 → 上下文选择 → 带来源证据 → 当前 Codex。内部指标兼容增加可选 snapshot/revision，原有未提供身份的 run-only 生产者仍可使用；公开 HTTP/CLI、EF/DF/DI 协议、单位及判断标准保持。

| 文件 | 改动目的 |
|---|---|
| `query-agent/src/query_agent/domain/experiment.py` | 内部指标携带可选 snapshot/revision，scope 保留原身份。 |
| `query-agent/src/query_agent/adapters/data_foundation/experiments.py` | 从已经核验的 DF scope 复制真实身份，不从用户问题补造身份。 |
| `query-agent/src/query_agent/application/context/resolver.py` | 在比较、冲突与新鲜度分析前，筛选请求明确指定的 snapshot/revision。 |
| `query-agent/src/query_agent/application/collection.py` | 证据传递身份；同一原件出现在不同快照时，证据 ID 区分作用域；旧无快照指标的证据 ID 保持。 |
| `query-agent/tests/contract/test_data_foundation_adapter.py` | 原 HTTP 夹具验证完整身份、正确/错误快照、错误 revision 和原 run-only 路径。 |
| `query-agent/tests/unit/test_experiment_context.py` | 验证其他快照不会污染指定快照的冲突分析、证据身份不混淆及旧 ID 兼容。 |

`EvidenceScope.matches` 的严格匹配规则没有放宽，没有增加原始数据旁路、fallback、模型调用或查询框架。

## 短验证

先增加回归，在修复前重现 6 项失败；修复后该组检查通过。另从源码构建 wheel，独立安装到 `var/business/a33-query-snapshot-scope-20261025/query-runtime`，使用现有 GCD/JPEG 的公开 EF/DF 数据做前后对照。

| 场景 | 旧包 | 新包 |
|---|---|---|
| 正确的 ORFS snapshot + revision + run | 两设计都误报资料不足 | 两设计都 ANSWERED，身份及指标与原结果一致 |
| 请求只有路径事实的 OpenSTA snapshot | 本轮不重测旧包 | NEEDS_MORE_DATA，证据为空，不借用 ORFS 的指标 |
| 正确 snapshot + 错误 revision | 本轮不重测旧包 | NEEDS_MORE_DATA，证据为空 |
| 原 run-only 查询 | 已有可用记录 | 继续 ANSWERED，并保留 DF 的真实身份 |

10/10 安装包验证通过，其中包括 2 份旧包故障复现及 8 份新包正反例。GCD 核查节点 WNS=0 ns；JPEG 核查节点 WNS=−0.0156584 ns。它们是既有节点的查询验证，不是新的最终 PPA 实验；该 JPEG 节点时序仍不合格。

本次 GCD 首对旧/新查询都约 6.77 秒，其余约 0.33–0.52 秒；不据此声称性能提升。新增 EDA/模型调用均为零，原实验与产物未写入。

## code-check 实际结果

- Ruff 与格式检查通过；Pyright：0 errors。
- 三条模块导入约束全部通过，application 没有导入具体 DF/EF 实现。
- Query 完整回归 179 项通过；最终针对性检查 25 项通过。
- 根业务 Query/专业交接/事实材料化相关回归 27 项通过。
- 逐文件差异检查通过，没有削弱旧断言或修改其他专业算法。
- 独立安装包 `pip check` 通过；4 个产品源码文件与 wheel 字节哈希一致。
- 26 个用户在途文件保持原哈希；没有提交用户的 DF/DI 或评测修改。

测试夹具的类型错误在检查过程中修正后重新通过类型及针对性检查；失败日志保留。以上是实际执行的本地代码检查和短验证记录。

wheel SHA256：`53439ee58764699c05480cf4dd260920c7d170f89181b8eff6b12df318b82940`。所有日志、前后原响应、命令、来源及身份检查收据位于 `var/business/a33-query-snapshot-scope-20261025`，关键文件为 `installed-verification.json`、`artifact-and-protection-check.json` 和 `verified-query-runtime.json`。

## 接下来

这项具体阻断已修复并通过工程验证，老板仍可独立核查。新包验证发生在本轮隔离环境；旧运行配置没有被批量改写。后续运行清单必须显式使用 `verified-query-runtime.json` 指向的已验证解释器/wheel，不能只更新源码就假设生产已经启用。

长实验仍暂停。下一步固定实际资源与运行配置，再处理 GCD/Nangate45 500 ps 条件及对应 PDK 兼容阻断；每项继续采用同样的四步流程，不混在一个补丁里。

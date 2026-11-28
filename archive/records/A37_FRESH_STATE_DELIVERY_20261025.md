# A37：验证新布局产物真正进入数据与 Query 链

本轮接续 A36，产品源码没有变化。复用刚完成的三个 DPL 诊断布局，不重新运行布局、优化搜索或模型；新增 EDA 只有三次原生 OpenDB 事实导出，均由 EF 执行。

## 验证内容与结果

通过现有命令证据 bundle/manifest 核验三个实际输出 ODB 的 SHA 与成功生产者 `run-d3e32e96004041ea9ff1e06b568b8c47` 对应，再分别经 EF OpenDB adapter 导出、DF 公共导入、DI 读取与 A33 已安装 Query 包查询。

| 布局 | 新事实导出 EF run | 同一单元 `_496_` 的位置（µm） | 查询原件 |
|---|---|---|---|
| Diamond | `run-0d8d92f8564f4de3a6a2ae1a5593c022` | (18.43, 8.4) | `d3f00fb46b4c…` ODB |
| negotiation | `run-92414862385f48da81fd0963689e6d18` | (18.43, 9.8) | `d91364e83293…` ODB |
| evolve | `run-eadceca8ce604e85815c2121d4f8ab4a` | (17.48, 8.4) | `8153fb5a99d6…` ODB |

三份快照的 run subject 都是同一生产者，但 snapshot/revision 分别明确区分；每份查询均检查实际 scope、位置、单位、对象身份与原件 SHA。不是拿上一次成功结果代替新结果。每份有711个 instance；例如 evolve 事实含4842个实体/物理上下文、9457条关系，汇总、实体上下文和物理上下文通过现有 DI 入口可查询。

`location of instance _496_` 三次均 `ANSWERED`，不启动额外 hosted 模型。两项边界也实际检查：

- 指定 Diamond snapshot 却要求 evolve revision：`NEEDS_MORE_DATA`，0条证据，没有跨状态泄漏。
- 向只有布局几何的快照索要最终 WNS：`NEEDS_MORE_DATA`，0条证据，没有借用旧时序或捏造当前指标。

这验证的是新执行产物到可查询设计状态的交付。三个布局不是完整 routed PPA，不记为新500ps baseline或三条正式优化结果。

## 恢复与封装

对三个已导入产物各调用现有 `import_snapshot` 续接，实际只发生六次 GET（读取原回执/快照），没有 POST、EDA重算或重复导入。导入回执内容保持。Agent不需要访问底座内部数据库或手动解析ODB。

最初检查脚本错误地期待每个 command capture 文件都对应独立 artifact，提交新 EDA 前停止；现有 command 本来用已登记 evidence bundle 及文件 manifest 保存输出。修正检查脚本为复用既有 `stage_facts.bundle`，没有因此增加一层产物服务或改历史契约，原诊断错误日志保留。

## code-check 与留存

没有产品、模块或测试源码修改，因此复用相同源码的 A36 静态/类型/格式与658项根回归，不为文档重复跑全场。新增临时检查脚本语法检查通过；本轮实际边界验证为3个新导出/导入/位置正例、1个错revision负例、1个缺时序负例，以及3次只读幂等续接。26个用户保护文件SHA保持，未重启服务、改容量或发布用户在途代码。

运行证据：`var/business/a37-fresh-state-delivery-20261025/` 的 `fresh-delivery-receipt.json`、`query-position-check.json`、`scope-and-reuse-check.json`、`placement-without-final-timing-query.json`；各快照、SDK回包与Query证据保存在其 runtime 实验目录。完整SHA与manifest在原件中，运行数据不提交Git。

本轮仅修改本报告、TASKS、ARCHITECTURE、STATUS以记录已核查功能与下一步。整体目标仍未完成；继续处理专业策略与剩余实际任务的阻断，长优化搜索尚未放行。

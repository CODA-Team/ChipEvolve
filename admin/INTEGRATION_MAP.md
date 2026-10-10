# Agentic EDA 版本与接入关系

现有六个模块保留独立仓库与职责。源码审计基线记录在 [P0 证据清单](/home/wjyuan/reports/agentic-eda-p0-20261009/evidence/manifest.json)。

| 对象 | 正式开发位置 | 当前接入状态 |
|---|---|---|
| Execution Foundation | `execution-foundation` | 已有执行能力，阶段接入前修复实测取消与列表问题。 |
| Data Foundation | `data-foundation` | 已有快照与查询能力，需可靠导入指定实验产物。 |
| Data Interface | `data-interface` | SDK，沿用公开契约。 |
| Query Agent | `query-agent` | host 模式可用，Flow 交接待接收器实现。 |
| Toolkits | `toolkits` | 现有固定流程保留，新增 A2 原生阶段接点。 |
| A2 Flow | `flow-agent` | 从 `/home/wjyuan/flow-agent` 完整源码封存后建立正式仓库；P1 独立运行副本待验收。 |

A2 算法负责阶段屏障、候选生成、淘汰与检查点继承；EF 负责物理任务排队与进程。接点位于 `run_stage.sh` 到 `run_make.sh` 的单候选阶段边界，CP0 评价同样纳入统一执行。

旧服务、数据库、原生运行目录及用户未提交修改保留。运行状态与产物放在 `var`。Code 项目的工具链独立冻结，不强行换成 Flow 的工具版本。

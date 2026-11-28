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

Nangate45 AES 原设计缺少参数消费 hook，生成的布线调整值未影响物理执行；修复提交 `57be217` 分别接入 floorplan 与 post-CTS routing，保持原默认 0.5/0.25 容量。当前运行副本保持原源码并完整封存，修复后的源码另开完整实验再验收。

A2 算法负责阶段屏障、候选生成、淘汰与检查点继承；EF 负责物理任务排队与进程。接点位于 `run_stage.sh` 到 `run_make.sh` 的单候选阶段边界，CP0 评价同样纳入统一执行。

旧服务、数据库、原生运行目录及用户未提交修改保留。运行状态与产物放在 `var`。Code 项目的工具链独立冻结，不强行换成 Flow 的工具版本。

## P3 源码决定的实施边界

2026-10-10 续接审计核对了 `flow/run_stage.sh`、`run_make.sh`、`eval_tns.sh`、`maindriver.sh` 和 Toolkits 的 `openroad/a2_stage.py` / `a2_checkpoint.py`。以下为施工依据，尚未计作已交付能力。

- 物理接点：`run_make.sh` 单 slot 调用阶段 adapter。保留 `run_stage.sh` 的整批阶段屏障与候选数；controller 不占用 EF 的物理 worker 再等待子任务。
- 上游交接：通过原生 DRP 已核实的 checkpoint hash 找到实际 donor 的 EF `flow_archive`，按 artifact_id 提交 CTS/route。新配置与新 SDC 独立提交，不把旧 archive 中的参数冒充新参数。返回产物投影到原生 results/logs/objects/reports，继续沿用原有 DRP、lineage 和指标解析。
- 日志要求：stage archive 已含祖先日志，不重复 append 同一祖先输出；评价 log 保存真实工具输出，继续由原生固定 CP0 逻辑读取。评价任务明确指向该次物理 run，回流 signed TNS/WNS 和 power 及实际 SPEF/时钟/库条件。
- 提交恢复：在发 HTTP 请求前持久保存完整任务与 `campaign/iteration/candidate/stage` 幂等键。中断后查询或重提交同一请求，复用已成功的 run/artifact，不能给已完成阶段创建新物理任务。
- campaign 恢复：新增显式恢复入口，复用 manifest 和 LLM ledger，不调用 `state.py invalidate`、campaign-start-guard 或 ledger init 重建实验，不执行已完成 iteration 的清理。`-F` 仍代表归档重开，与恢复互斥。
- 原生决策恢复：在配置生成、两次物理阶段/DRP、布线、评价、备份与跨轮优化边界保存已提交状态。已完成模型决策不再次请求；未提交的 DRP 操作先恢复其输入与候选状态再执行，不能在被部分修改的配置/lineage 上盲目重跑。已有 immutable result_dump 保留并核对，不覆盖。
- 验收：实际终止 controller 后恢复同一 campaign，比较恢复前后的 EF run_id/产物 hash/调用账本，确认已完成物理任务和决策未重复。另测提交已受理但本地尚未记录 run_id 的窗口。P2 的单阶段成功不替代这一验收。

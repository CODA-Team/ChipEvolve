# A42：Flow 已完成反馈按 DF 回执接续

基线根 `942c1fa`、Flow `99007aa`。本轮继续逐功能审计，不启动长搜索、新 EDA、模型调用或服务更新。Flow 的模型错误透传已在当前 `llm_client.py` 中实现，复用原检查，不重复修补。

## 具体问题与修复

`platform_feedback.publish_feedback` 在已有成功入库回执时仍无条件 POST `/snapshots/from-run`。因此，导入完成但响应丢失，或完成后的写入口暂时不可用时，读取已有结果也依赖重复写请求。这里不是宣称此前 25 份反馈导入失败：实际检查发现它们均已 imported、attempts1。

本轮从其中一份真实反馈复制出私有状态，以真实 EF 只读客户端核对同一 producer/原 metadata，在导入 POST 前设置禁止写入的诊断拦截。原实现确实到达 POST 而无法接续；没有实际向生产 DF 发送故障 POST 或停止服务。

修复仅为先 GET 既有 `/imports/<artifact_id>` 回执；明确 HTTP404 时才沿原路径 POST 导入并读取回执。其他错误继续透传，不猜测任务不存在，不增加自动重跑、后台循环、服务/API/数据库。原 EF 导出、排队/运行预算、metadata SHA、snapshot/physical/producer 关系及 attempts1 检查全部保持。完成响应丢失后也能沿原回执继续，不新增 EDA 或导出任务。

## 文件职责与验证

| 修改文件 | 职责 |
|---|---|
| `flow-agent/flow/platform_feedback.py` | 反馈导入前解析已有 DF 回执；只改这一交接行为 |
| `flow-agent/flow/test/test_platform_feedback.py` | 模拟真实404/丢响应/503状态，核对不重复 POST、同一 EF export、原身份检查保持；完善同一测试客户端和 HTTPError 类型夹具 |

修改前 3 失败/4 通过；修改后 7 项针对性检查通过。`dev.py flow-agent check` 完整 **99 项通过**，根业务 **670 项通过**；Ruff、格式、两个修改文件 Pyright、diff 检查通过。最初静态诊断已在相同两文件修正，未批量格式化或重构原代码。

25 份真实 GCD/Nangate45 CP0 反馈的私有副本分别调用现有原生函数：生产 EF `run/artifacts` 与 DF 查询均实际执行，DF **50 GET/0 POST**；全部保持原 snapshot、producer、physical run、summary 和 import receipt，零新增 EF/模型/优化调用。禁止 POST/submit/cancel 的诊断拦截确保未以重算换恢复成功。原25份记录和26份用户保护文件 SHA 不变，公开 EF 活跃队列为空。

这些是原 Flow 的 CP0 评价事实，不是最终共同测量或新的 PPA 收益；其中存在负时序，不能据此宣称候选可采用。当前运行/历史副本不热改；下一次从正式 Flow 源冻结的任务才消费此修复。

## 原件及续接

证据位于 `var/business/a42-flow-feedback-recovery-20261025/`：`baseline.json`、`before-actual-recovery.json`、`after-actual-recovery.json`、`code-check.json`、`test-before.log`、`targeted-final.log`、`module-check.log`、`root-regression.log` 及最终静态日志。广目录文件名扫描过慢，已停止该只读扫描，改为读取明确实验的25个回执；未操作实验进程。

后续若改变反馈入库行为，只修改原 `platform_feedback.py`，数据继续沿原 EF metadata→Toolkits export→DF receipt→native Flow，不新增接入层。另已定位文档化 `comparisons.replay_goal` 仍固定 ASAP7 的 RC 目录，下一切片修其跨 PDK 固定方法重放。全目标、完整设计证明、八组双次 PPA 尚未完成，长实验保持暂停。

# A25：原生正式试验的超时收尾资格

正式对照必须记录预算耗尽后遗留的后台工作。源码核查确认：现有原生 Codex 记录器在超时或外层中断时只停止自有前端树，独立 EF 任务仍由 EF 运行。已有记录器明确披露了这个范围，但尚未提供试验结束时的 EF 收尾配置。不能由“前端已停止”推断“整场计算已停止”。

## 最小接点与边界

隔离候选 `1448c0c` 基于集成候选 `36a806a`，已发布至 ChipEvolve 的 `a25-native-episode-ef-timeout-20261019` 分支。只有三份改动：

| 文件 | 职责 |
|---|---|
| `admin/run_native_codex_episode.py` | 五行接点：派发前准备显式收尾配置；自有前端确认停止后执行收尾并记录结果 |
| `admin/native_episode_cleanup.py` | 校验已绑定 SHA 的部署及显式新试验范围；复用现有 `Jobs.cancel_active`，经公开 EF 确认终态 |
| `admin/test_native_episode_cleanup.py` | 八项场景，覆盖真实前端超时、业务/验证子任务和原生 Flow 范围、其他试验隔离、旧默认及未确认终态 |

原生 Codex 继续负责推理、规划和工具循环。新增部分属于既有试验记录器的确定性预算收尾；没有新调度服务、数据库或模型 harness，也没有改变专业算法、原目标、PPA 筛选和公开 EF/DF/SDK 契约。生产源码、运行中的 JPEG、GCD 待命副本均未切换。

可选的 `platform_timeout_cleanup` 使用下列私有记录器配置：

```json
{
  "config": "/absolute/deployment.json",
  "experiments": [
    {"design_id": "gcd", "key": "unique-trial-flow"},
    {"design_id": "gcd", "key": "unique-trial-validation/logic"}
  ],
  "settle_seconds": 30
}
```

部署文件必须列入本次 `input_hashes`；范围必须在该设计目录内且派发前尚未存在。正式清单需显式列出所有计划使用的业务、候选与验证子范围。没有该配置时保留原行为；正常完成不触发取消。预算结束/外层中断与普通业务观察进程断线恢复分别处理：后者可在仍运行的 Codex episode 内恢复原 EF 任务。

数据流为：原生前端超时 → 原前端树停止确认 → 已登记业务范围 → 既有 `Jobs.cancel_active`（含原生 Flow journal）→ 公开 EF 取消与终态 → 原 episode 回执。取消请求、最终终态和错误分别保留，未确认时标为 `incomplete`。`settle_seconds` 是发出取消后的终态观察窗口，不是所有 HTTP 操作的总硬截止；实际全部收尾墙钟计入 episode 成本，正式协议仍需冻结总预算及失败判定，不可宣称此字段提供整场严格期限。

## 工程证据

将新检查配合原记录器执行，出现五项失败、三项通过：原记录器未进行 EF 收尾，也未在派发前核查范围。恢复候选后，针对原记录器及新行为共 23 项通过；整个集成根回归 553 项通过。两个生产文件 Pyright 零错误/警告，三份文件 Ruff F/格式、差异及模块边界检查通过。默认观察/恢复能力保留；直接 helper 检查中的三项基线通过不误写成旧记录器已具备功能。

## 真实公开 EF 验证

使用生产 caller Python 和其已安装 SDK，运行可控 Python 前端夹具；未调用真实模型或 EDA 工具。前端在独立新试验范围登记一个真实 EF 排队任务后到达五秒预算。记录器停止该前端，经既有 EF 接口取消本试验任务，确认终态 `cancelled`，完整 episode 墙钟约 5.263 秒。

- 本试验任务：`run-75761524ab7c4a4ca364e44102bddb54`，由新增收尾完成取消。
- 同设计、另一试验的控制任务：`run-19028272091141909dd2b5a1b833ef67`，在上述收尾后仍为 queued；随后由夹具显式清理。
- 当前 JPEG PDR `run-eb41635685744cd78abc20d5bd0c3b1f` 仍 running，原 JPEG 共同测量 `run-51e140c2d7ee439981c0a804c34f3094` 仍 queued，未被取消。

两份夹具 EF 任务均最终 cancelled，started_at 为空且没有工具 attempt；真实模型调用和 EDA 命令数为零，宿主/服务/测试成本未知而非零。夹具记录器的预期返回码 1 和不完整模型 usage 原样保留，未将夹具称为原生 Codex 正式试次。该次实际验证覆盖排队任务取消；运行中 EDA 的终止不由这个夹具证明，仍结合既有 EF 真实取消资格与后续正式试次核查。

证据：`var/business/a25-native-episode-ef-timeout-20261019/acceptance.json`、`public-ef-qualification-r1/acceptance.json`、`teardown-acceptance.json`、原/候选检查日志及 XML。当前 JPEG 完整证明已从匹配推进到 partition，原串行交付及 GCD 待命仍继续。A25 未冻结，完整专业接力及 A26–A28 仍待完成。

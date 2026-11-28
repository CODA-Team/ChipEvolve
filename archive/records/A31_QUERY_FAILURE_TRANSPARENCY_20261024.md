# A31.3：Query 原生失败原因贯通业务入口

本切片解决“Query 没有回答，但老板和控制 Agent 不知道为什么”的问题。原 JPEG/Nangate45 调查实际收到模型容量不足错误，执行了零个数据工具，原业务报错却只说明没有最终诊断。

## 改动与数据流

| 文件 | 职责 |
|---|---|
| `query-agent/src/query_agent/adapters/llm/codex_host.py` | 保留原生 `error`、`turn.failed` 消息，向收据与调查状态传递错误、退出码、追踪目录；后续成功 turn 清除先前瞬态错误。 |
| `query-agent/src/query_agent/application/investigation.py` | 内部收尾函数接受可选失败说明，保留终态及预算耗尽的优先级。 |
| `query-agent/tests/contract/test_host_failure_receipt.py` | 验证两种原生事件、瞬态恢复、预算优先级、终态保持与只启动一个宿主。 |
| `chip_evolve/diagnosis.py` | 无最终证据回答时，把调查的停止原因继续交给控制 Agent。 |
| `admin/test_query_objective_handoff.py` | 验证业务报错保留原生原因和追踪位置。 |

原生事件 → Query 模型适配器 → 调查收尾/持久状态 → 现有业务诊断入口。没有新增模型循环、服务、公共 CLI 或 EF/DF/DI 协议，也没有自动重试或切模型。

## 验证

- Query：Ruff、格式、Pyright、三条导入依赖约束全部通过，170 项回归通过。
- 根业务：Ruff、格式、Pyright 通过，636 项主回归通过。另在具有 Pydantic 的 Query 开发环境运行用户现有 evaluation 测试，24 项通过；未修改这些文件。
- 初次把两组测试混用一个环境时，测试环境缺 Pydantic；反向混用时缺新版 Toolkits objectives。分别用各自适用环境运行后全部通过，没有用产品源码补丁掩盖环境差异。
- 新 wheel SHA256：`8d995865a3753671973947f2a8b100a489a7e31d1117a621b255acae1a50d763`。已离线安装至本轮专用 `query-runtime`，`pip check` 通过，生产服务和旧 Query 环境未切换。
- 安装包消费原 JPEG 容量不足事件的重放通过，状态为 paused，含原报错、exit_code=1 与 trace 路径；这是旧真实事件的确定性重放，新增模型调用和 EDA 调用均为零，不是新的线上容量失败。
- 当前源码的 GCD 真实宿主调查成功，4 条证据，约 73.09 秒；确认 setup TNS=0、worst slack=+0.0143074 ns，因此 WNS=0 ns。全程只读，无新增 EDA。

## 已发现但本切片不扩修

简单 `ask` 的 run/snapshot 证据匹配及 typed timing evidence 选择仍可返回 NEEDS_MORE_DATA。原始 smoke 输出保留；不能将其写成完整简单查询验收通过。正式 investigation 路径已真实回答，但本次消耗 239567 input token（其中 cached 200960）、1707 output token，尚不能证明节约 token/时间。

运行证据统一位于 `var/business/a31-result-recovery-20261024`，含 `query-live-receipt.json`、`query-original-failure-replay-receipt.json`、两设计查询输出、wheel 和独立运行环境。

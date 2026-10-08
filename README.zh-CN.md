# Execution Foundation 0.2

给 AI/Agent 使用的单机执行底座：提交真实工具任务，查询进度、失败、资源、日志、产物；取消、重试与追溯。Python 标准库，无账号、无 UI、无业务数据库联查。

```bash
python3 ../dev.py execution-foundation check
bash tools/start-platform.sh
```

默认入口 `http://127.0.0.1:18700`，一个进程运行 API 和 worker，状态写入 `../var/execution-foundation`。`/kernel/health` 提供 worker 心跳、队列与能力准入状态；`/health` 是同一结果。仅支持本机 loopback。启动参数可配置 state/plugins/admissions/input roots、CPU/内存预算；`--api-only` 才使用外部 worker。

公共 Python client 的 `KernelClient.submit()` 接收 schema_version=3 的 TaskSpec。API：`/kernel/runs`、单次 run 的 `/cancel`、`/retry`、`/logs`、`/resources`、`/timeline`、`/metrics`、`/artifacts`。数据底座通过已注册的产物 HTTP 导入，禁止读执行数据库。

工具接入遵守 [插件契约](docs/PLUGIN_PROTOCOL.agent.md)，算法只在外部插件。插件准入属于执行底座；输入冻结、输入/产物路径限制、进程树治理和产物 hash 核验不会因精简被删除。目录和废弃功能变化见 [移除记录](docs/REMOVED_COMPONENTS.md)。

相对直接终端操作的验收目标是完整生命周期与可重复追溯。一次短工具调用可能增加成本；实测证据见工作区 benchmark 报告，不能把 fixture 测试当真实 EDA 性能。

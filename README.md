# data-interface

独立项目，负责对外接口契约和标准库 Python SDK。安装包名称与原实现保持一致，保留其文件 Git 历史。

从上级工作区使用：

```bash
python3 dev.py data-interface check
python3 dev.py data-interface shell
```

Data Interface 没有独立服务进程，没有运行依赖。
公开契约见 CONTRACT.md，SDK 通过 `from eda_ai_client import EdaAiClient` 使用。
默认显式传入 Data Foundation 的 data_url；原始产物工具另需 Execution Foundation
的 kernel_url。SDK 不导入任何应用内部源码。

先前 API 和工具使用说明见 docs/original-project-readme.md（原 monorepo 安装路径
已成为历史示例）。迁移来源见 MIGRATION_SOURCE.json；完整工作区说明见上级 README。

## 0.2 boundary

发布 15 个工具 schema、标准库 HTTP SDK 和 py.typed。设计目录、名称解析、快照选择、指标归属都由服务处理；执行 run 的过滤/分页及产物 kind 过滤传到 EF。SDK 不做 N+1 聚合。名称与 object_id 必须显式区分，URL 编码保留斜杠、加号、百分号和字面 net: 前缀。

curl/urllib 同样能调用这些 API。SDK 的收益是多 Agent 复用同一参数和错误语义，不能宣称查询或模型推理更快。调用者检查 status、missing 和 evidence 后再使用结果；breaking changes 必须升级契约。
# Explicit analysis operations (SDK 0.2.2)

Fact methods and `read_query` use GET and do not start an EDA process. The SDK
also exposes an explicit creation boundary for a caller that chooses to obtain
new evidence:

```python
result = client.create_analysis(snapshot_id, "timing-overview", {
    "startpoint": "source/Q", "endpoint": "sink/D", "check": "setup",
    "limit": 1, "wait_seconds": 120,
})
native = client.create_native_query(snapshot_id, {
    "script": "report_wns", "with_timing": True, "wait_seconds": 0,
})
observed = client.get_native_query(native["data"]["run_id"], wait_seconds=10)
```

Creation options, scope resolution, input availability, results and errors are
owned by Data Foundation. Toolkits builds native operations and Execution
Foundation manages their tasks. The SDK preserves the public envelope and has
no execution engine, parser or database. `get_native_query` only reads or waits
for an existing task. Neither read method calls a creation method.

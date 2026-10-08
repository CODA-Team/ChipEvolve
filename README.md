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

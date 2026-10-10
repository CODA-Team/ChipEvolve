# 工作区规则

本工作区包含 Execution Foundation、Data Foundation、Data Interface、Query Agent、Toolkits 和 Flow Agent 六个独立 Git 项目；进入对应项目后读取其 AGENTS.md。

- 后续开发只修改这里的正式项目。旧路径是运行基线或历史证据。
- Query Agent 主实现来自独立 `/home/wjyuan/query-agent`，不是历史 `apps/query_agent`。
- Data Interface 是接口契约和 SDK，不新增后台服务或数据库。
- 各项目自己的 editable 安装可用于开发；跨项目依赖必须通过 wheel 或 HTTP。
- 不添加跨源码目录的 PYTHONPATH、sys.path 修改或兼容软链接。
- 运行数据属于 var；不写入源码目录，不自动连接旧实验数据库。
- 默认通过 dev.py 使用项目虚拟环境，避免用户 site-packages 和本机代理串扰。
- 保留未提交用户修改。不要把现有功能缺口记作已完成。
- 旧生产服务、历史 worktree 和大型数据迁移是独立操作，需要核查消费者后再执行。

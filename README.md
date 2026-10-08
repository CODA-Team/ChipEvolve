# Execution Foundation

独立执行平台：管理执行生命周期、工作空间、资源、原始产物、身份和溯源。
领域解析器仍在 plugins，kernel 只使用公共契约。架构约束见 AGENTS.md。

Data Foundation 和 Query Agent 已移出本仓库；接口 SDK 归 Data Interface。
项目通过 contracts/client wheel 和公开 HTTP API 交互。这里不安装其他项目源码。
独立 Query Agent 是上层主实现；原 apps/query_agent 代码留在迁移前基线。

使用自己的 .venv。统一入口从上级工作区执行：

```bash
python3 dev.py execution-foundation check
python3 dev.py execution-foundation serve
```

`serve` 只在 127.0.0.1:18700 启动开发 gateway；`tools/start-platform.sh`
在新状态目录启动 gateway、worker 和 plan executor（18840），不会接入旧数据库。
跨项目/论文验收测试的迁移归属见上级 admin/migration-manifest.json。
kernel、plugin、gateway 和 guardrails 原始实现及门禁完整保留。

共享依赖 wheel 由上级 admin/bootstrap.py 构建；消费项目安装发布产物，不能使用
跨项目 PYTHONPATH。原始提交与过滤历史映射见 MIGRATION_SOURCE.json 和
.git/filter-repo/commit-map。这里只使用迁移主分支，不是旧实验 worktree。

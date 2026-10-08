# 质量门禁

运行本项目独立环境里的 pip check、pytest（contracts/runtime/guardian/registry/provenance/HTTP）、G1–G17 及负例、源码 mypy、变更 Python 的 Ruff/Black、git diff --check。GitHub Actions 执行相同门禁。

0.2 删除的账户/控制台/编排应用测试对应已经删除的职责；保留的执行行为必须继续验证。HTTP 新增幂等提交、进度、资源、原始产物/hash、取消、不存在的 run、旧入口失效、loopback 限制和不可伪造的执行上下文测试。

17 条规则没有放宽。应用相关门禁继续作为未来独立应用的规则并保留负例。记录的源码规模只能缩小；历史批准不能变成无限增长通行证。类型检查仅扫描各公共包的 src，构建输出不属于源码。

真实 OpenROAD 与 Codex 对照由上级 admin/benchmarks 运行。数据、wheel 安装、调用事件、资源和失败记录保存在上级 var/benchmarks，结论保存在工程验收报告。一次短命令可能因基础设施增加耗时，必须如实报告。

# 单机执行底座的边界

0.2 移除 identity 账户/会话/资源归属数据库、Gateway 的 app 配置/导航/代理，及 dse_lab、evidence_console、run_console、plan_executor。历史代码与测试仍可在 0.1 Git 提交中查看，旧服务器运行目录未改变。

删除的是这些产品特定职责，不是执行可靠性门禁。保留 17 条架构门禁及负例，保留 runtime/guardian/store/registry/provenance/contracts 的完整测试。新增 HTTP 验收覆盖单机 submit/idempotency/progress/resource/artifact/cancel/error 与不存在的旧入口。源码大小门槛没有放宽。

启动一个 loopback 服务时内置 worker；另一个独立 worker 只在显式 --api-only 部署时需要。无账号、无用户配置、无后台 Web 应用。插件准入、输入根目录约束、产物 containment、SHA256 校验与持久化记录仍在。共享主机的本地用户仍属于同一信任边界；远程入口不在此版本范围内。

商业适配器保留外部插件身份；其存在不构成真实工具验收成功。OpenROAD 真实试验与测试 fixture 结果分别报告。

# 服务器项目与环境核查（2026-10-08）

四个正式开发项目集中在 `/home/wjyuan/projects/eda-development`，各自拥有 Git、虚拟环境、锁文件、职责说明和独立检查。主 Query Agent 使用原独立项目，Data Interface 是 SDK，不运行服务。整理与真实验收见 [工程报告](admin/ACCEPTANCE_REPORT.md)。

## 原有混乱与本轮修复

- 原仓库混合执行、数据、另一套 Query Agent、SDK、控制台及实验结果；四个项目已独立。
- SDK 曾聚合设计目录、解析名称、判断指标归属；这些业务归回 Data Foundation。
- 执行底座已删除账号/会话、应用代理、旧控制台、plan executor；单机 loopback API 与 worker 同进程。
- Query Agent 已安装公共 SDK，设计与时序数据接通；29 个原类型错误已修复。继承的 import-linter 配置原本执行 0 条契约，现真实执行 3 条。
- 本机代理绕过、独立解释器、公开 wheel 依赖、源码/运行状态分离已经验证；bootstrap 已实际完成，四环境无跨项目 editable。
- 废弃的 12 个旧 wheel 归档到 var/archive/wheels-before-refinement。当前 wheelhouse 仅保存活跃包和开发工具。
- 开发服务入口为 18700（EF）与 18924（DF），数据只进入新 var；默认不加载旧数据库。

## 原运行区的核查记录

服务器多人共用。原 execution foundation 有多个 Git worktree，日期目录也包含交付和实验消费者。迁移时确认在线 DF 数据库约 80.98GB，另有 df-scratch 与 eda-ai-data 大数据库；未复制或删除。旧服务、旧工作树、论文交付保留原位，未重启或停止。

本轮是独立开发区整理与工程改进，没有把旧生产服务切换到新代码。旧运行区仍应按消费者与在途实验清单迁移，不能依据名称或日期直接删除。
原始机器核查在 admin/server-inventory.json；迁移路径在 admin/migration-manifest.json；迁移阶段报告完整保存在 admin/server-audit-migration-baseline.md。

## 当前验证与限制

最终独立检查、wheel 真实 OpenROAD 闭环、取消/重启、Codex 对照和未完成能力均记录在 admin/ACCEPTANCE_REPORT.md。早期的 admin/verification.json 是迁移检查，当前结果以 admin/final-verification.json 为准。

Typed 关系/物理查询、自动补分析、自主诊断/优化尚未实现。真实验收仅三缓冲链 STA，不能代表完整芯片 PnR 或商业工具验证。

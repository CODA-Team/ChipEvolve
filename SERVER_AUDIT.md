# 服务器开发区核查与整理结果

2026-10-08（北京时间）。范围为 wjyuan 用户的 EDA 项目与相关服务；服务器由多人共用，未修改其他用户和系统级环境。

## 已确认的问题

1. 原 execution foundation 仓库同时承载执行平台、Data Foundation、另一套 Query Agent 服务、Data Interface SDK、论文验收和实验结果。仓库职责与开发依赖混在一起。
2. 独立 query-agent 和 apps/query_agent 是不同实现。按用户选择，以独立项目为主，完整保留其 15 个已修改文件和一个未追踪测试文件；原工作树未改动。
3. Data Interface 原来没有独立仓库，实际包括 CONTRACT.md 与 eda-ai-client。现作为接口/SDK 项目独立，不增设后台服务。
4. gateway、worker、plan executor 和 Data Foundation 共用旧 execution foundation/.venv；Data Foundation 还通过 PYTHONPATH 加载源码。编辑源文件可能让下一次重启加载与当前运行不同的代码。
5. 日期命名目录并非全是拷贝：原 execution foundation 有 7 个 Git worktree，其中 3 个在 /var/tmp。直接移动或删除会破坏工作树登记或实验消费者。
6. 在线 Data Foundation 使用约 80.98 GB 的实验数据库；home 下另有约 63.3 GB 的 df-scratch 顶层数据库和约 69.4 GB 的 eda-ai-data 顶层数据库。仅统计已列出的文件，不代表目录总占用。未复制或删除这些数据。
7. 全局 HTTP_PROXY/HTTPS_PROXY 存在而本机绕过项缺失；经代理访问 localhost 发生超时。直接连接后，8700、8840、8924 的主要服务健康检查通过。新开发入口显式配置 localhost 绕过代理。
8. PID 1890221 的旧 demo 服务仍监听 8080，其工作目录已经被删除。保留进程并记录，未根据目录缺失就擅自终止。

## 已完成的整理

四个独立项目位于本工作区：execution-foundation、query-agent、data-foundation、data-interface。分别拥有独立 Git、虚拟环境、编辑器解释器和依赖锁文件。提取项目保留对应路径的历史及旧/新提交映射；Git remotes 未自动发布到任何远端。

Execution Foundation 已移除 Data Foundation、历史 Query Agent 服务和 SDK 的当前源码，保留原 kernel、gateway、plugin 和架构门禁。Data Foundation 的 35 个测试文件随项目迁出，SDK 的测试文件随接口项目迁出。12 个跨项目/论文测试文件在 admin/legacy-integration 清单中保留，完整 fixture 和原验收运行方式仍属于旧基线。

共享 contracts/client 使用本地发布 wheel；Data Foundation 的 runtime wheel 仅供已有测试 fixture 使用。各环境的 editable 安装都指向本项目，没有跨项目 editable 或源码路径注入。干净开发启动端口为 18700（kernel）、18840（plan executor）、18924（Data Foundation），数据写入本工作区 var。

Data Foundation 原来根据 monorepo 相对路径寻找 producer 和 contracts 来计算 source_fingerprint；拆分后改为覆盖服务和已安装公共包的内容。外部 producer 的溯源由快照证据负责。其原始 flow 默认路径也已移除机器绝对路径，改为运行配置。

## 验证

| 项目 | 测试结果 |
| --- | --- |
| Execution Foundation | 475 通过，1 项按宿主能力跳过；含全部架构门禁 |
| Data Foundation | 334 通过；临时 HTTP 服务 smoke 通过 |
| Query Agent | 78 通过；ruff、格式、import-linter 通过 |
| Data Interface | 6 通过 |

总计 893 项通过、1 项跳过。所有环境的 pip check 通过。另从与源码无关的临时目录安装纯 wheel，验证 SDK→Data Foundation、SDK→Execution Foundation、主 Query Agent→Execution Foundation 的真实 HTTP 边界；未使用旧运行数据库。服务指纹在 wheel 与开发安装间一致。

Query Agent 的 pyright 存在 29 个原有错误，涉及执行 HTTP 响应的整数类型处理以及未提交测试中的类型标注。原 src/tests/docs 与新项目逐文件哈希一致，证明并非本次迁移引入；没有修改这些功能代码来隐藏问题。明细见 admin/query-pyright.log。

## 剩余边界

独立 Query Agent 的设计数据 provider 当前仍返回 unavailable；接入 Data Interface SDK 是后续功能工作。已有三个可用 HTTP 边界不代表该缺口已实现。

本次完成独立开发区建设，旧运行区尚未切换：旧服务、原主工作树、日期 worktree、论文交付和数据库均保留原位。后续运行迁移应先确认在途执行与消费者，准备持久化状态与切换验证，再迁服务；历史清理应根据消费者清单归档，而不是直接删日期目录。

完整机器可读记录：admin/server-inventory.json、admin/migration-manifest.json、admin/verification.json。使用说明见 README.md，编辑器入口是 eda-development.code-workspace。

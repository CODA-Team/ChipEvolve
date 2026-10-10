# EDA 独立开发工作区

这里是六个独立项目后续开发的统一入口。2026-10-10 已确认 Agentic EDA 施工规划，当前进行 Flow 的真实多轮原生验收。施工进度见 [STATUS](admin/STATUS.md)，目标和验收见 [PROJECT_CONTRACT](admin/PROJECT_CONTRACT.md)。原有模块迁移日期：2026-10-08（北京时间）。

| 项目 | 源码目录 | 职责 | 跨项目交互 |
| --- | --- | --- | --- |
| Execution Foundation | `execution-foundation/` | 执行、工作空间、资源、原始产物、溯源 | 公开 HTTP API；发布 contracts/client wheel |
| Query Agent | `query-agent/` | 问题规划、证据收集、可回答性、回答 | Data Interface wheel + 两个服务的 HTTP |
| Data Foundation | `data-foundation/` | 快照、设计对象、结构化事实、查询、独立数据库 | 安装 contracts/client wheel；HTTP 读取执行产物 |
| Data Interface | `data-interface/` | 公开工具契约、Python SDK、响应语义 | 标准库 HTTP 客户端，没有服务进程和数据库 |
| Toolkits | `toolkits/` | OpenROAD/ORFS 命令、输入加载、原生解析和导出 | 安装 contracts/client wheel；生成运行清单，调用 EF HTTP |
| Flow Agent | `flow-agent/` | A2 原生候选搜索、阶段淘汰与优化状态 | 原生基线正在验收；统一阶段执行待接入 |

每个项目都有独立 `.git`、`.venv` 和 `environment.lock.txt`。禁止用 `PYTHONPATH`、软链接或另一项目的 editable 安装来跨源码边界。共享包在 `wheelhouse/` 发布；Data Foundation 中的 runtime 包仅用于现有测试 fixture，不是其运行依赖。

```text
Query Agent（调查） --安装包--> Toolkits --HTTP--> Execution Foundation
Query Agent --已安装 SDK--> Data Interface SDK --HTTP--> Data Foundation
Data Foundation --HTTP--> Execution Foundation 原始产物 / 执行能力
Data Foundation --安装包--> contracts + client（Execution Foundation 发布）
```

独立 Query Agent 是主实现。原 execution foundation 内的 `apps/query_agent` 是另一套历史服务实现，没有合并进主实现，也没有伪装成它的适配器；完整代码和历史保留在旧基线。

## 使用

从本目录执行，不需要激活全局环境：

```bash
python3 dev.py query-agent python -m query_agent.interfaces.cli --help
python3 dev.py query-agent check
python3 dev.py data-foundation check
python3 dev.py data-interface check
python3 dev.py execution-foundation check
python3 dev.py toolkits check
python3 dev.py data-foundation smoke
python3 dev.py query-agent shell
```

`dev.py` 清除继承的 Python 环境路径，禁用用户 site-packages，并让 localhost 绕过代理。`check` 执行依赖与独立测试；Query Agent 还执行 Ruff、格式、严格 Pyright 和三条 import-linter 契约，Execution Foundation 执行源码 mypy 与 G1–G17 门禁。最终验收与对照结论见 `admin/ACCEPTANCE_REPORT.md`；迁移阶段记录在 `admin/verification.json`。原 29 个类型错误已修复。

干净开发服务使用新端口和持久化目录，启动后在当前终端运行：

```bash
python3 dev.py execution-foundation serve  # 127.0.0.1:18700
python3 dev.py data-foundation serve       # 127.0.0.1:18924
```

开发运行数据属于 `var/`；现有实验数据库不会自动导入。Data Foundation 若需要执行能力，显式传入 `--kernel-url http://127.0.0.1:18700`。原始 ORFS 流程目录显式使用 `--native-root` 指定。SDK 安装依赖为零，Query Agent 使用 CLI。
Toolkit 的 OpenROAD 启动器显式读取 `EDA_ORFS_IMAGE`；共享工具镜像与源码环境分开。

## 来源和运行基线

`/home/wjyuan/execution foundation` 保留为当前服务与历史实验的迁移前基线；`/home/wjyuan/query-agent` 保留为独立 Query Agent 原始工作树。后续开发使用本工作区。Query Agent 的原有修改和未追踪文件完整保留，并随工程改进纳入本地提交；整理前补丁备份在 `admin/query-agent-working-tree.patch`。

提取项目保留对应文件的 Git 历史；旧提交映射在各自 `.git/filter-repo/commit-map`。每个项目的 `MIGRATION_SOURCE.json` 记录原始路径及提交。详细迁移路径和测试归属在 `admin/migration-manifest.json`。

日期命名目录与 `/var/tmp/eda-ai-pilot` 下的工作树、论文交付、实验结果和大数据库均保留原位。它们不属于新的开发源码。没有重启旧服务，没有移动数据库，没有删除工作树；80 GB 的在线数据库仍使用原路径。

重新建立环境可运行 `admin/.venv/bin/python admin/bootstrap.py`。本地 wheel 校验值在 `wheelhouse/sha256.json`，精确已安装环境记录在每个项目的 lock 文件。发布共享包后需要重新构建 wheel 并明确更新消费环境。

## 当前工程验收

Execution Foundation 仅本机单用户，一个 HTTP+worker 进程；没有账户/会话数据库、旧控制台或 plan executor。Data Foundation 拥有设计目录、唯一快照解析、对象匹配与指标归属；SDK 不再承载这些业务。主 Query Agent 已通过 SDK 连接对象、时序数据和实验比较，已接通关系、完整 fanout、位置/区域、实例变更和显式补 STA。新增调查支持
固定范围、假设/反证、来源展开、恢复、预算与真实 Codex ECO 交接；效果须按
本轮封存对照单独验收，不能把 answered 状态当作正确答案。

迁移阶段的 OpenROAD 验收是 Nangate45 三缓冲链 STA（理想网络）。本轮新增完整
Nangate45/GCD ORFS 流程；第一次导出清单遗漏的失败记录与修复后的成功记录均在
`var/sprints/20261008-141846/`。72 题和模型诊断验收按本轮计划单独报告，历史
Codex 对照在 `var/benchmarks`，不能替代新对照。

## 历史成果核查与下一阶段研究

2026-10-08 的[项目核查报告](admin/research/PROJECT_AUDIT_20261008.md)记录 Data Foundation 的历史代码保留、论文原始汇总复核、Execution Foundation 残留和主 Query Agent 的实际缺口。[Query Agent 科研地图与建设方案](admin/research/QUERY_AGENT_RESEARCH_AND_PLAN_20261008.md)给出数据获取、调查技能、自适应深度、补充分析和任务交接的设计与分阶段验收。

历史数据实验支持当时整套数据能力的作用，尚未证明拆分后的各项目贡献或主 Query Agent 的诊断效果。本轮已实施新调查工作流与独立 Toolkits，新对照题集和运行器已固定，效果由本轮正式测量单独报告。只读[复核脚本](admin/research/reproduce_audit.py)及其运行命令随核查报告保存；运行证据属于 `var/research/20261008/`。

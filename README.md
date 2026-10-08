# EDA 独立开发工作区

这里是四个项目后续开发的统一入口。迁移日期：2026-10-08（北京时间）。

| 项目 | 源码目录 | 职责 | 跨项目交互 |
| --- | --- | --- | --- |
| Execution Foundation | `execution-foundation/` | 执行、工作空间、资源、原始产物、溯源 | 公开 HTTP API；发布 contracts/client wheel |
| Query Agent | `query-agent/` | 问题规划、证据收集、可回答性、回答 | 执行平台 HTTP；设计数据端口仍待实现 |
| Data Foundation | `data-foundation/` | 快照、设计对象、结构化事实、查询、独立数据库 | 安装 contracts/client wheel；HTTP 读取执行产物 |
| Data Interface | `data-interface/` | 公开工具契约、Python SDK、响应语义 | 标准库 HTTP 客户端，没有服务进程和数据库 |

每个项目都有独立 `.git`、`.venv` 和 `environment.lock.txt`。禁止用 `PYTHONPATH`、软链接或另一项目的 editable 安装来跨源码边界。共享包在 `wheelhouse/` 发布；Data Foundation 中的 runtime 包仅用于现有测试 fixture，不是其运行依赖。

```text
Query Agent（独立原项目） --HTTP--> Execution Foundation
Query Agent --设计数据端口待实现--> Data Interface SDK --HTTP--> Data Foundation
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
python3 dev.py data-foundation smoke
python3 dev.py query-agent shell
```

`dev.py` 清除继承的 Python 环境路径，禁用用户 site-packages，并让 localhost 绕过代理。`check` 执行依赖检查与项目测试；完整验证结果见 `admin/verification.json`。Query Agent 的原有未提交代码仍有 29 个 pyright 错误，详见 `SERVER_AUDIT.md`。

干净开发服务使用新端口和持久化目录，启动后在当前终端运行：

```bash
python3 dev.py execution-foundation serve  # 127.0.0.1:18700
python3 dev.py data-foundation serve       # 127.0.0.1:18924
```

开发运行数据属于 `var/`；现有实验数据库不会自动导入。Data Foundation 若需要执行能力，显式传入 `--kernel-url http://127.0.0.1:18700`。原始 ORFS 流程目录显式使用 `--native-root` 指定。SDK 安装依赖为零，Query Agent 使用 CLI。

## 来源和运行基线

`/home/wjyuan/execution foundation` 保留为当前服务与历史实验的迁移前基线；`/home/wjyuan/query-agent` 保留为独立 Query Agent 原始工作树。后续开发使用本工作区。Query Agent 的全部未提交修改和未追踪文件已经复制到新主项目，仍保持未提交状态；补丁备份在 `admin/query-agent-working-tree.patch`。

提取项目保留对应文件的 Git 历史；旧提交映射在各自 `.git/filter-repo/commit-map`。每个项目的 `MIGRATION_SOURCE.json` 记录原始路径及提交。详细迁移路径和测试归属在 `admin/migration-manifest.json`。

日期命名目录与 `/var/tmp/eda-ai-pilot` 下的工作树、论文交付、实验结果和大数据库均保留原位。它们不属于新的开发源码。没有重启旧服务，没有移动数据库，没有删除工作树；80 GB 的在线数据库仍使用原路径。

重新建立环境可运行 `admin/.venv/bin/python admin/bootstrap.py`。本地 wheel 校验值在 `wheelhouse/sha256.json`，精确已安装环境记录在每个项目的 lock 文件。发布共享包后需要重新构建 wheel 并明确更新消费环境。

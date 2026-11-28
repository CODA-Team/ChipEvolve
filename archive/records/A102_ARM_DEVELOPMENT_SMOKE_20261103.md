# A102：鲲鹏开发环境与 smoke 验证

日期：2026-11-03，北京时间。接续 A101 核心迁移，补齐开发依赖、源码编辑安装、可重复检查入口及实际 EF→OpenROAD→DF/DI 短验证。未启动模型调用或专业优化搜索。

## 交付与验收范围

鲲鹏工作区为 `/share/home/yuanwenjie/chipevolve-migration-20261102/projects/eda-development`。根项目及九个独立模块源码、Git 历史、专业源码和既有在途修改已迁入。A101 十一个用户修改文件和十七个根目录修改/未跟踪文件的哈希核验保留；本轮不提交或覆盖这些用户修改。

各项目 `.venv` 补齐开发工具；可安装项目仅将自己的源码设为 editable，跨项目继续使用已安装 wheel 或 HTTP。Flow、DPL、ECO 保留原有脚本布局和独立环境。开发检查工具版本与源机对齐。

| 检查范围 | 鲲鹏实测结果 |
|---|---|
| 根业务回归 | 771 passed |
| Execution Foundation | 391 passed，6 skipped；依赖及 mypy 通过 |
| Data Foundation | 381 passed；依赖及独立 HTTP smoke 通过 |
| Data Interface | 13 passed |
| Query Agent | 228 passed；Ruff、格式、Pyright、三条依赖约束通过 |
| Toolkits | 78 passed；依赖和 F 类静态检查通过 |
| Flow Agent | 99 passed；标准 `dev.py flow-agent smoke` 通过 |
| GoalEvolve | 459 passed，71 subtests passed；一轮四 Student 控制流程 mock smoke 通过 |
| TimingECOAgent | 67 passed，2 subtests passed |
| DPLEvolve | 知识索引和仓库检查通过；一轮三 Student 任务包和命令生成 dry-run 通过 |

EF 的跳过项包括本机支持进程树测量时不适用的拒绝场景，以及未安装的商业工具/旧服务器 Toolkit 布局检查。当前共同 OpenROAD 的实际运行另有真实 GCD 验证，不用这些条件跳过代替验收。

专业控制流程的 mock、任务包 dry-run 和单元测试都不算 EDA 优化或 PPA 收益；本轮没有新增两次优化的平均值。

## 运行环境与开发环境

现有三个服务保持原接口和数据路径：EF 执行 `60749`、历史 EF API-only `60748`、统一 DF `60752`。历史 EF 无执行 worker；两份历史 DF 库只读，新事实仍写入独立验证库。

服务解释器移到：

- `runtime/envs/services-execution`：固定 EF 与 Toolkits wheel，历史 EF 共用该固定环境。
- `runtime/envs/services-data`：固定 DF 及其依赖 wheel。

EF 插件解释器也指向固定运行环境，避免编辑 `toolkits/.venv` 对服务中的后续任务生效。服务启动命令仍在 `runtime/run-executor.sh`、`run-archive.sh`、`run-data.sh`，没有增加服务或平台 API。

项目 `.venv` 用于开发。需要部署修改时，显式构建 wheel、更新对应运行环境并重启所需服务。本轮已将 DF 的 SQLite 修复构建成 wheel 并安装到固定 DF 环境，记录包 SHA 和服务指纹。

持久数据、构建缓存和生产临时目录均在 `/share`。一键开发检查仅将可丢弃的测试夹具放到专属 `/dev/shm` 内存目录，结束后清理；该目录不占系统磁盘，也不存实验产物。测试日志与核验收据保存在 `/share`。

## 本轮修复

| 文件 | 原问题与修改 |
|---|---|
| `dev.py` | Flow smoke 错用 `tests` 目录；改用原 `flow/test` 和正确工作目录，其他模块入口不变 |
| `admin/test_local_business.py` | 测试写死旧机 `/usr/bin/python3.12`；使用当前解释器，SDC 字符串仅换行排版，字节不变 |
| `admin/run_goalevolve_native.py` | 旧独立复现工具取消时快照会漏掉枚举期间新生的跨会话子进程；先冻结所属父子树，再终止已识别的进程组，保留 PID 起始时间检查 |
| `admin/test_goalevolve_native_runner.py` | 新增取消期间派生进程的真实竞态回归；原跨会话夹具留出启动时间，仍检查预算结束和所有子进程退出 |
| `admin/test_native_codex_episode.py` | 超时夹具需先完成输入哈希并输出开始事件；将测试预算留足启动时间，仍保留超时、清理、原始 trace 和未知用量断言，生产预算不变 |
| `flow-agent/flow/test/test_platform_execution.py` | 假 API 每次构造 ZIP 带入当前时间戳，慢环境下哈希不同；固定测试 ZIP 元数据，生产哈希检查保留 |
| `data-foundation/src/openroad_app_data_foundation/source_json.py` | SQLite 新版 `bad JSON path:` 与旧版报错不同；两种已知路径错误都返回既有 ValueError，其他数据库错误继续抛出 |
| `data-foundation/tests/test_eda_source_json.py` | 增加两种 SQLite 路径错误和非路径数据库错误的三项回归 |
| `data-foundation/smoke.py` | 独立服务启动等待从 10 秒改为 30 秒，避免共享盘冷启动导致假失败；查询与断言不变 |

没有更改专业算法、PPA 目标、候选晋升规则或历史结果。取消修复只属于旧 `admin` 复现记录器，现行业务实验继续由 EF 监督。

## 真实功能 smoke

通过当前隔离后的 EF 和固定 Toolkits 读取原 GCD G02 ODB，再导入 DF 并通过 DI 查询：

- EF run：`run-2bcaaf05c5d84d5bb4eb8d1a0c521663`。
- snapshot：`a102-arm-development-gcd-opendb`。
- 原件 SHA：`8c4c183c47460fa8c5294350f4db09e5138377ea049bd1f2fec01bc5aaf4c27f`。
- 作用域和阶段摘要 available；对象查询按 limit=3 返回 truncated，目录共有 2738 个对象，保留精确原件引用。这不是 2738 个标准单元。

本步骤只读原设计、提取事实，没有重新布局布线或改变原测量值。

## 开发操作

```bash
ssh kunpeng-direct
cd /share/home/yuanwenjie/chipevolve-migration-20261102
source runtime/environment.sh
cd projects/eda-development
python3 dev.py data-interface smoke
python3 dev.py flow-agent smoke
```

运行全部 Python 开发检查，使用已配置的临时内存目录：

```bash
/share/home/yuanwenjie/chipevolve-migration-20261102/runtime/dev-smoke.sh
```

运行单个模块：

```bash
/share/home/yuanwenjie/chipevolve-migration-20261102/runtime/dev-smoke.sh query-agent
/share/home/yuanwenjie/chipevolve-migration-20261102/runtime/dev-smoke.sh goal
```

该脚本复用现有 dev.py、pytest 和 DPL 检查，不调用模型，不启动专业 C++ 构建或优化搜索。开发修改在相应项目自己的 `.venv` 生效；跨项目修改需要重新构建并安装公共 wheel。

## 证据和后续工作

目标机完整记录位于 `migration-evidence/development-smoke`，包含首次失败、环境安装、修复后测试、固定服务环境、包 SHA、DPL dry-run、Goal mock 控制流程和真实 GCD smoke。保留最初错误，不用最终通过覆盖原失败收据。

后续要启动新的专业优化，仍需分别完成候选 C++ 的 ARM 构建验收，并显式配置设计、PDK、时钟、目标、专业 profile 及相应评价工具。`runtime/inspection.json` 保持迁移检查用途。旧 `query-agent ask` 混合面积问法的指标别名问题仍单独记录，不把本轮单元测试通过解释成所有自然语言查询质量均已解决。

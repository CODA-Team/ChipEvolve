# L3：GoalEvolve 本机复现进展与环境边界

状态：进行中，未完成切片验收。已确认施工计划；环境、AE-1、模拟 smoke、AST 初始化、真实 AES AE-2 重放及本机 p0 基线冻结通过。AE-3 新源码演化尚未启动，模型入口选择待老板回复；上游历史资产相关测试仍有失败，不记全套回归通过。

## 老板现在已经得到的效果

- GoalEvolve 有独立正式源码和本机实验环境，未覆盖 Flow 或 DPLEvolve 的工具。
- 原项目发布的 AES / ASAP7 源码可以在本机重新编译、跑真实物理流程、生成产物，并通过官方四项结构检查。
- 时序、动态功耗和漏电功耗与已发布结果在原有容差内一致；这证明复现可运行，不是本轮新优化收益。
- 真实基线与新源码演化分开留证。统一 EF 执行、统一 DF 数据和三项目协同仍由 L4/L6/L7 实施，本轮不冒充已接入。

## 三个项目的工具环境如何处理

| 项目 | 当前复现条件 | 执行管理现状 |
|---|---|---|
| Flow / A2-ORFO | 既有冻结 A2/ORFS/OpenROAD 环境；AES / Nangate45 | 已通过 EF 的真实阶段执行与数据回流验收。 |
| DPLEvolve / ReviewDSE | 独立上游、原项目 OpenROAD anchor `55cb44c`、共享 core 与私有候选构建；GCD / Nangate45 | 原生复现通过，EF/DF 接入待 L4/L6。 |
| GoalEvolve | 独立上游、内容冻结的 p0 与已发布候选源码；AES / ASAP7 | AE-2 重放通过；原生新演化和统一接入尚未完成。 |

统一执行入口不等于统一工具版本。每个任务绑定自己的源码身份、二进制、编译依赖、工艺库、输入和脚本；Python 环境独立，兼容的主机编译依赖可以复用，环境变量仅影响该任务的进程。

协同阶段必须实际验证：不同版本 ODB 能否读取；源码补丁能否在共同基线上构建；命令、网表、DEF、SDC 和工艺库语义是否兼容。ODB 不兼容时，通过已验证的网表/DEF/SDC 与原工艺库重新导入或重跑对应阶段。最终收益使用同一设计输入、工艺和评价条件；不能把 AES / ASAP7 与 AES / Nangate45 混比，也不能把同名设计当成同一输入。

本轮未证明三个工具已能相互接力。环境并存已准备；兼容构建和完整接力分别是后续接入及 L7 验收内容。

## 固定来源与运行环境

- 正式独立仓库：`/home/wjyuan/projects/eda-development/goalevolve`；上游 `https://github.com/CODA-Team/GoalEvolve.git`，固定 `1cc20aa611e687c2745ff7da6a006a5d25f49f85`。
- 运行根：`/home/wjyuan/projects/eda-development/var/code-agent/l3-goalevolve-20261011`；运行副本及原生 outputs、工具链、构建、日志、campaign 均在 var 内。
- p0 内容摘要：`357addea0e53ed786d7b37c8d763b711e4531789b0d93c87878c8d1d4cd91f69`。来源 commit 为 `d231bd8f98d2a0adb8369002b2c1e7aa8e7877ed`，捕获时含工作树修改，身份使用内容摘要。
- 原生 Miniforge/setup 环境：Python **3.12.15**、tree-sitter **0.26.0**、tree-sitter-cpp **0.23.4**；项目要求 Python 3.12，主机已有的 3.12.13 与本环境补丁版本不同。`conda-explicit.txt` 保存实际包集合。
- GCC **13.3.1**、CMake **3.31.9**，复用 `/opt/EDAs/OpenROAD-flow-scripts/shared/dependencies`；实际编译器路径在 CMakeCache 中确认，二进制与动态链接记录在 `toolchain-records/`。
- `inputs-manifest.json` 冻结 **41** 个 AES 设计/ASAP7 文件。官方 checker、parser、控制源码与实验模板单独纳入 `qualification/control-manifest.json`。
- 实测 p0 的 `openroad -version` 输出上级工程提交标签 `1006208…`，不能当作 OpenROAD 源码版本。VCS-free 快照的 CMake 版本生成可向上找到容器仓库 Git；以源快照内容摘要、私有构建及二进制 hash 作为身份依据，原始版本标签分别保留在 `toolchain-records/version-label-audit.json`。没有为修饰标签重跑已验证的实验。
- 运行副本仅预配置 Teacher/Student 模型名为 `gpt-6.1-sol`，保留 `xhigh`、原重试/预算/方法。未调用模型，未添加或输出凭据；正式上游配置未修改。

## 已完成的原生验证

| 验证 | 结果与含义 |
|---|---|
| 原生 `make setup` / `make check` | 成功；AE-1 发布资产、快照内容与主机基础检查通过。 |
| `goalevolve.cli smoke --rounds 1` | 成功，**模拟 evaluator**；仅为控制流程检查。 |
| `p0 init` / AST | 成功；保留四个 Student、AST、EPD、原晋升策略、`rsz/rmp` 可编辑范围。 |
| 原生 AE-2 preflight | p0 私有二进制可运行，发布源码内容校验通过；preflight 与正式重放分别留证。 |
| AES AE-2 | 从冻结发布源码独立构建并真实重放；flow/parser/checker 退出 0，发布三项容差全部通过。 |
| 本机 p0 baseline | 构建/flow/解析/布局/官方检查通过，真实测量已冻结，`baseline_frozen_ready`。 |
| 一轮 AE-3 | 尚未启动；没有本轮新 C++ 候选或新优化收益。 |

AES AE-2 实际数值：

| 指标 | 发布参考 | 本机结果 | 原有绝对容差 |
|---|---:|---:|---:|
| \|TNS\|，ns | 15.572590769 | 15.57（官方 CSV） | 0.05 |
| 动态功耗，pW | 335,607,141,000 | 335,607,135,653.86224 | 1,000,000,000 |
| 漏电功耗，pW | 29,093,000 | 29,092,669.13775 | 1,000,000 |

精确 post-route checkpoint 的 TNS 为 **15.5725907688 ns**；官方 CSV 保留两位小数。布局合法，slew/cap/fanout 三类 DRV 均为零。原生日志 flow runtime **235 秒**，CSV tool runtime **210 秒**；包括构建的 AE-2 步骤为 **996.64 秒**。

本机 p0 基线为 **TNS 12.37 ns、动态功耗 427,394,076,214.0958 pW、漏电功耗 95,383,300.50418 pW**；DRV 为零，flow runtime 75 秒、tool runtime 59 秒，含构建步骤 1104.66 秒。基线来自本机真实测量，不使用历史输入 CSV。AE-2 发布候选使用自身固定 Tcl/recipe，不能把它与默认 p0 基线的差异算成本轮新源码收益。

四项官方结构检查是固定 physical cell、macro、I/O 位置和 FF/clock 完整性，**不是完整布尔逻辑等价证明**。本轮不把结构检查表述为完整逻辑等价。

## 当前未完成项与实测问题

1. 原项目 `goalevolve/agents/codex_runtime.py` 从项目 API dotenv 生成隔离 Codex 环境，不支持直接使用现有 Codex 登录。本机现有入口是 Codex 登录；待老板选择提供已有 API 配置文件路径，或允许独立运行副本适配登录入口。EDA 重放不依赖这个选择；新演化依赖它。
2. 未修改上游的单元测试在本机 localhost 绕过代理后为 **343 passed、9 failed、24 subtests passed**。六项失败引用未发布的历史 local profile，一项普通 evolve profile 指向缺失的历史父代源码，两项依赖未提供的跨设计知识文档。失败详情保留，未补造历史事实，未删除或放宽测试。
3. 首次全套运行副本测试为 **362 passed、10 failed、24 subtests passed**（含 20 项 artifact 测试）；运行副本的 portable-profile 测试首先在固定 `gpt-5.6-terra` 模型名断言失败；未修改上游的同一测试则在缺失历史父代源码处失败，原因分别保留。另有一项是 localhost 被代理转发后返回 502。运行工具已只对 localhost/127.0.0.1 绕过代理，复查该问题消失。历史九项仍存在，不宣称全套回归通过。已搜索本机完整 clone 的 Git 历史，六份 local 配置和跨设计知识文件均未找到被提交的版本，证据为 `missing-assets-audit.json`。
4. 两次调用准备错误（不存在的 dependencies Python 路径、显式指定不存在的 tests/integration）均留有失败回执；随后使用实际原生 Python / 已存在的测试路径，不归因于 GoalEvolve 算法。

## 本轮文件与工程检查

| 文件 | 职责与改动原因 |
|---|---|
| `.gitignore` | 登记独立 GoalEvolve 仓库，避免重复纳入根源码。 |
| `admin/run_goalevolve_native.py` | 有界记录原生命令、控制身份、总预算、日志和失败；清理原生 EDA/Codex 另开会话的子进程。仅为开发验证工具。 |
| `admin/test_goalevolve_native_runner.py` | 验证失败留证、不覆盖、冻结来源、总预算与跨会话清理。 |
| `admin/accept_goalevolve_native.py` | 核对真实测量、发布容差、新 C++ 修改、来源、有效性与未完成门禁；缺少真实结果不得通过。 |
| `admin/test_goalevolve_native_acceptance.py` | 拒绝模拟/未改源码、错误指标、缺 checker/二进制和非零 DRV。 |
| `admin/L3_GOALEVOLVE_PLAN_20261011.md` | 记录计划已获确认。 |
| `admin/L3_GOALEVOLVE_REPORT_20261011.md` | 当前实测结果、环境分工和未完成项。 |
| `TASKS.md` / `admin/STATUS.md` | 更新真实阶段，不把准备或模拟记作完成。 |

新增工具 lint、类型、格式检查及 **12 项测试**通过；连同既有恢复/资源/DPLEvolve 检查共 **37 项**通过，既有数据来源检查 **4 项**通过。上游九项失败和 AE-3 缺口意味着 L3 尚未通过全部门禁。

没有修改 EF、DF、DI、Query、Toolkits、Flow 或 DPLEvolve 业务实现及公共契约，没有新增跨项目源码导入、PYTHONPATH 或兼容软链接。原生 check/pytest 自身的本项目导入方式沿用上游。已有 `admin/evaluation` 用户修改未纳入本轮；旧服务和数据库未动。

## 证据与续接

运行根下的 `qualification/steps/*/receipt.json` 保存每步原始命令、退出码、时间、配置/日志 hash 与控制变化；`source/outputs/ae2/aes_cipher_top_student_code/report/ae2_report.json` 为成功的原生发布对照。`engineering-checks/receipt.json`、`inputs-manifest.json`、`toolchain-records/` 和原测试日志可只读核查。

p0 campaign：`p0/aes_cipher_top/l3_aes_20261011`。成功基线应由原生 `p0 baseline` 冻结；目标为 TNS 12 ns、动态功耗 350,000,000,000 pW、漏电功耗 35,000,000 pW。不得使用输入 CSV 的历史值替代本机基线，或把已发布 AE-2 候选当成本轮 AE-3 新候选。

下一步先解决模型入口选择和上游测试资产缺口，然后冻结最终运行控制，按已确认计划运行一轮四 Student 的真实 AE-3。切片未完成前不进入 L4，不自动扩大设计或轮数。

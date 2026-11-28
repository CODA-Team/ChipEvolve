# U3：DPLEvolve 共同工具链与统一执行报告

状态：U3 工程验收通过；业务验收待老板。真实演化、固定源码独立重放和五项门禁均已完成；停止在 U3 边界。

## 当前业务结果

DPLEvolve 已在 Flow 采用的共同基础源码和镜像上成功构建，并通过公共 Execution Foundation 执行真实 GCD 输入生成、三条原生基线及新源码候选构建/评价。Teacher/Student 的专业机制、候选试验及晋升规则由原项目管理。统一设计数据入口、GoalEvolve 和最终三项目 PPA 接力仍未交付。

老板目前得到的是：可在本机共同环境中运行的 DPLEvolve，以及由执行底座统一管理的构建/评价、固定候选来源和可重放证据。不是只跑 dry-run；本轮使用真实 GCD/Nangate45、665 个可移动实例和真实源码修改。最终 HPWL 比同环境 Diamond 减少 3.53%，比项目自带 framework 减少 0.73%；位移尾部回归和未产生收益的机制同时保留。

共同基础：ORFS `5105b0a77fe8b3ae107bed67112eb5f83caca5d5`、OpenROAD `27288f5c90265ae5296b2f5a9fa6e8714fa191ad`、OpenSTA `e983e15b2cb346badf8f23725fd3914d25312c44`，SIF 内容 SHA256 `8e6ee7aac233da078364649fa8111dac5de33a3589f5445dcffd96f9d6d8dd39`。不跟随移动的 latest。

本轮专业补丁后的准备提交另行记录：ORFS `49bc9d62aa74715ff60967e099f5fd37e38ea2e3`、OpenROAD `58e77cbebea15fbc28c687e1ed3a343d04022cee`；`prepared-source.json` 固定 11,144 个源码文件的实际内容。共享 core 目录名 `95283bf` 是早期准备标签，不代表最终准备提交。控制源码 r1–r9 均保存；Teacher/Student 的既有 helper 从 r8 生成，实验 profile 的确定性 leaf 指向 r9，未覆盖 r8。

本轮证据根目录：`var/code-agent/u3-dplevolve-common-20261013/`。根基线、八模块状态及用户修改保存在 `preparation/baseline.json`；正式业务代码修改只在批准的 DPLEvolve/根验收工具范围内。历史数据库、生产服务及其他用户进程不变。

## 三条真实基线

使用本轮新生成的 GCD/Nangate45 `3_4_place_resized.odb` 和 SDC；输入来自真实 RTL、共同 ORFS 和明确的本轮 source-built OpenROAD。HPWL 是原生 pin-based 线长，不是 cell-bbox proxy，也不是最终布线 PPA。

| 原生比较线 | HPWL（µm） | 原生运行时间（s） | 合法性 |
|---|---:|---:|---|
| Diamond 参考线 `openroad_dpl_flow` | 3206.7 | 0.588 | 通过 |
| negotiation `openroad_dpl_negotiation` | 3142.1 | 0.595 | 通过 |
| 项目自带框架 `evolve_default` | 3116.3 | 0.780 | 通过 |

新版 OpenROAD 的默认算法已由 Diamond 切换到 negotiation，旧 `-use_negotiation` 参数移除。老板明确同意：共同模式显式选择 Diamond，negotiation 使用新版默认入口；旧原生模式保持原调用。三条比较线的算法含义及原生晋升目标保留，不能把两个相同算法的调用包装为两条基线。

## 接入和关键修复

`DPL_EVOLVE_PLATFORM_PROFILE` 显式选择共同环境与统一执行。共享构建、私有 variant relink 和原生 baseline 的三个低层入口委派到 EF；生成的 Student build/fresh-build/evaluate helper 也经过同一入口。没有 profile 时保留原生复现方式，平台模式失败不会退回宿主独立执行。

HTTP 承载控制信息、状态和产物引用，已注册大文件经现有公共定位/本机复制及 hash 校验取回。构建证据包不冒充 DF 设计快照；本轮没有实现 L5/L6 的统一数据查询契约。

共用核心与候选工具分别记录实际来源、CMake 配置及二进制 hash。CMake 在源码路径生成版本头、消息清单和 STA 文档，构建使用独立的私有源码副本承接这些产物，原始冻结源码保持不变。OpenDB 指针容器改用其新版 `PtrMap/PtrSet`，仍按对象 ID 比较；绘图接口适配新版 Qt-free core，不改变专业优化机制。

真实 Student 候选新增 Opendp 的实例状态，暴露了原生私有 relinker 的对象布局问题：共享 `OpenRoad.cc` 负责 new/delete，不能继续使用按旧头文件编译的对象。已在私有构建中用候选头文件重新编译该调用者，并替换私有链接配方中的对应对象；共享 core 及原候选算法不变。两次旧构建取消及修复轨迹保存，修复后的链接不再出现该 Opendp 构造/析构布局警告。

最终 Student 自己把状态改为按 Opendp 所属对象管理的 sidecar，保持外层类布局；私有调用者重编译仍保留，保证后续专业候选调整布局时不会继续链接旧调用者。上游 ABC 的既有链接警告仍有记录，不把它们与已修复的候选布局问题混淆。

## 真实候选与原生审阅

原生 Teacher 选择 framework 起点，要求 current-net producer → 原生 frontier handoff → exact transaction consumer → selected reorder 的完整机制。Student 修改真正的专业 C++ 源码，第一版合法结果为 HPWL 3093.5 µm、0.751 s，低于 1.176 s 原生 runtime gate；相对同环境 Diamond 减少约 3.53%，相对 framework 减少约 0.73%。平均/最大位移为 0.888751/10.649311 µm，665 个可移动实例。

Student 已完成原项目允许的一次有界强化，再补充阶段计时后完成最终验证。三次合法评价的最终 HPWL 均为 3093.5 µm，运行时间分别为 0.751、0.737、0.768 s。最终源码由原生 helper 保留为 `candidate/u3_gcd_source_20261013_iter_01_student_01_gcd_nangate45`，commit `9e8b70a80c0928a815d5f12ef14832aafbc1b6b7`，基点 `111fd34de8f66faa107ca80c1cbe8ec82d47dd1b`；干净工作区，`final_status=keep`，没有自动兜底源码提交。

Teacher review 正常完成，原生 `best_round_candidate` 离线核查也选中该候选，artifact 问题列表为空。这里只核查原生选择结果，没有发动下一轮、部署新默认工具或宣告老板业务验收。原项目的 5% 搜索参考尚未达到，差 47.135 µm。

归因：legalize 3352.1 → improve 3095.0 → mirror 3093.5 µm。相比 framework，improve 多恢复 23.9 µm，mirror 少贡献 1.1 µm，净改善 22.8 µm。消费者接受 93 个事务，selected reorder 接受 12 个窗口；内部累加收益不能独立等同最终收益。前段 producer 单移动可行性不足，强化的六个成对试验仍零接受。Teacher 判定机制链只部分有效，建议下一研究轮次重设计 producer，本切片不继续优化。

平均/最大位移由 framework 的约 0.8804/7.6964 增至 0.8888/10.6493 µm。最大位移尾部增加约 38.37%，原生合法性和 runtime gate 仍通过；不能隐藏这项回归，也不能将本次 HPWL 收益当作完整 PPA 改善。

真实实验仍由宿主 Codex 执行原生 Teacher/Student。三次模型操作均 returncode=0，无自动续跑；Teacher 规划 184.299 s，Student 4350.184 s（含同步等待构建/评价），Teacher 审阅 135.702 s。累计输入 18,949,218 token，其中缓存输入 18,557,312 token，输出 81,397 token；缓存为输入子集，不重复相加。未缓存输入 391,906 token。该计数包含长对话累计上下文，不等于付费金额或公平效率对照；费用未知。详见本轮 `preparation/model-usage.json`。

已逐项审查 Student 的 92 条已完成命令及生成 helper：真实三次构建/三次评价走原生入口与 EF；期间经公共 SDK 查日志、取消自己的旧兼容构建，无直接宿主 EDA 启动。只读命令/报告编写的失败也保留，未被计作实验收益。

## 改动文件与行为入口

| 文件（模块内路径除明确根文件外） | 职责与修改理由 |
|---|---|
| `metadata/common_toolchain.json` | 固定共同 ORFS/OpenROAD/STA/SIF 身份。 |
| `patches/common_toolchain/openroad_registration.patch` | 在新版生命周期与 Tcl/Python 链接中注册独立 evolve 模块。 |
| `patches/common_toolchain/orfs_run_arguments.patch` | 转发原生 evaluator 参数，保留新版 runner。 |
| `patches/common_toolchain/evolve_api.patch` | 适配新版 ID 指针容器和绘图 API，不修改优化算法。 |
| `patches/PATCH_AUDIT.yaml` | 将三份兼容补丁纳入原生准备审计。 |
| `scripts/workspace/prepare_workspace.sh` | 显式 profile 下准备共同 anchor 与三种专业起点；旧模式保留。 |
| `scripts/platform/execution.py` | 使用已安装公共 SDK 托管确定性操作、来源核查及产物留证。 |
| `scripts/workspace/build_openroad_only.sh` | 共享构建入口委派。 |
| `scripts/workspace/build_openroad_variant_relink.py` | 私有构建入口委派，并重编译接触候选对象布局的 OpenRoad.cc。格式整理及两处等价语法变化用于静态门禁。 |
| `baseline/run_baseline.sh` | 完整原生评价入口委派。 |
| `baseline/detail_place_openroad.tcl` | 共同环境显式 Diamond，保留旧模式。 |
| `baseline/detail_place_openroad_negotiation.tcl` | 共同环境默认 negotiation，旧模式保留旧参数。 |
| `validation/test_platform_execution.py` | 来源/失败/幂等/容器/两环境基线/私有布局回归，17 项。 |
| 模块 `AGENTS.md`、`scripts/README.md` | 说明 profile 入口及专业行为保持。 |
| 根 `admin/run_common_dplevolve.py` | 本机准备、真实运行、监督预算与固定源码独立重放。 |
| 根 `admin/accept_common_dplevolve.py` | 核对真实原始证据、公开 EF 产物、源码/binary/metrics 绑定和原生预算。 |
| 根 `admin/test_common_dplevolve.py` | 错配、损坏及 runtime gate 的 15 项验收回归。 |
| 根计划/本报告、`PROJECT.md`、`ARCHITECTURE.md`、`TASKS.md`、`admin/STATUS.md`、共同计划 | 记录能力、接口、证据和待业务验收边界。 |
| 根 `.gitmodules`、`SOURCE_MANIFEST.json`、`AGENTS.md`、DPLEvolve gitlink | 按已批准方案发布平台 fork，保留官方来源，不推原研究仓库。 |

数据流：Teacher 分配源码路线 → Student 私有源码 → 原生 build/evaluate helper → 薄 EF 桥接 → 固定共同容器/私有 binary → 原始指标与注册产物 → 原生 Student/Teacher 审阅 → Codex 与老板判断。专业算法行为在候选 C++ 源码改；执行/资源/证据行为在桥接和实验 profile 改；环境兼容在三份准备补丁和基线 Tcl 改。

## 工程验收与独立重放

- `steps/build-core-r8/receipt.json`：共享工具完整构建经 EF 成功；实际 OpenROAD 约 116 MiB。
- `preparation/source-reproduction-comparison.json`：发布准备补丁从干净共同版本独立重放，三起点及七组关键源码内容一致，10 项比较通过。初次仅有 GNU patch 备份文件差异，备份移入 preparation 保留，算法内容未变。
- 提交前对新补丁的空白/Tab 上下文做纯文本规范化，以通过完整 staged diff 格式检查，未修改 apply API 或源码。`preparation/patch-format-reproduction/receipt.json` 证明规范化前后应用后的 77 个文件一致；正式模块又从干净共同源码跑完整 prepare，`preparation/final-prepare-replay/receipt.json` 的三起点、专业模块、六共享文件与 ORFS runner 共 12 项核查通过。Git 元数据、来源路径 manifest 和保留的 GNU 备份单独保留，不当作算法内容比较。r8/r9 的原补丁和运行证据不覆盖，最终发布源码与它们生成的实际专业源码一致。
- `preparation/baseline-audit.json`：三条真实基线的原始日志、pin-based HPWL、检查命令、违规、运行时间核查通过。
- `steps/release-smoke/`、`gates/native-release-final.*`：原生编译、Shell、33 项知识索引、仓库补丁清单、Teacher dry-run 和生成 Student helper 检查通过。
- 桥接、原生/共同 Tcl 命令组装、幂等请求及私有对象布局测试 17 项通过；根验收测试 15 项通过。
- 相关 EF 资源/guardian 回归 34 项通过、1 项因本机可测进程树而条件跳过；Toolkits 全部 56 项通过。
- 既有原生验收/运行回归 16 项通过；本轮对应及相关测试合计 138 项通过、1 项条件跳过。静态→单元→差异审查→架构约束→回归依次通过，日志和顺序回执在 `gates/`。原生项目没有独立 C++ 算法单测目标，真实完整编译、合法评价和独立重放负责验证本次专业源码；不宣称已覆盖全部设计。

固定源码以新独立 clone、私有构建和 binary 重放；不是复用原候选 binary 或复制旧 metrics。构建 run `run-0e584433412d47b09958238a8ef058c2` 成功，`steps/evaluate-replay/receipt.json` 记录独立评价。最终 HPWL 3093.5 µm，所有阶段 HPWL、合法性和位移完全一致；runtime 为 1.008 s，低于原生 1.176 s 预算。允许正常时间波动，不要求独立 binary hash 相等。

`u3-acceptance.json` 的 **89 项核查全部通过**：三基线原始指标、13 个成功 EF 操作的来源/输入/原始注册产物、真实新源码、干净固定 ref、准确 source/binary/metrics 绑定、独立重放、原生 runtime budget 和工程门禁。另有 50 项架构/来源检查，包括保留用户修改、其他模块 HEAD、固定 wheel、11,144 个冻结源码文件及原四小时预算。

全部 21 个 EF run 的记录保留：13 成功、6 次早期共享构建失败、2 次旧候选构建主动取消。失败是准备/兼容修复轨迹，没有算作成功，也没有在失败后绕过 EF。摘要在 `preparation/operation-summary.json`，完整回执和日志在各 operations/steps 与 kernel 注册产物中。共享完整构建实测峰值约 42.8 GiB / 40 个进程；独立私有重放构建约 40.0 GiB / 26 个进程。64 GiB、2048 进程、8 编译线程、串行 LTRANS 的本轮预算保留，并非所有小任务都采用此额度。

老板可离线核查最终回执，无须启动 EDA 或模型：

```bash
admin/.venv/bin/python admin/accept_common_dplevolve.py audit --run-root var/code-agent/u3-dplevolve-common-20261013
```

这只是工程证据核查，业务效果由 Codex/老板根据事实判断。U4、整个 L4/L6/L7 和平台公平收益仍未完成。

## 下一步边界

本切片收尾后暂停，不自动发动新的研究轮次或 U4。接着应单独确认 GoalEvolve 的模型入口、AE-3 与共同工具链迁移切片，保留其四 Student、AST/EPD 和原生专业规则；再补齐其统一执行入口、按设计的数据/Query 交接，最后做同一设计/工艺/约束下的完整 Flow→两个 Code 接力及 PPA/token/耗时测量。Tutorial、新用户部署与论文公平对照暂缓。

## Git 检查点

DPLEvolve 平台适配已提交 `55ec40a1176fdf10cc4b18f81cf33a443881c030`，发布到明确的 ChipEvolve `modules/dplevolve` 分支；官方 `CODA-Team/DPLEvolve` 未推送，官方基点 `96d8c613d62bf3431083bb5e52c7df8853d5a622` 在 `SOURCE_MANIFEST.json` 保留。根仓库以 gitlink 固定该提交，检查点分支为 `u3-dplevolve-common-20261013`；实际根提交与远端核对回执保存到本轮 `publication.json`。

提交仅包含本切片源码、测试及项目资产；已有评测代码、DF/DI 用户修改、运行数据、候选源码仓库、凭据、wheel、venv 和镜像保留在本机原位置。独立候选研究 ref 位于本轮 var，不将它自动合入专业框架或默认工具。

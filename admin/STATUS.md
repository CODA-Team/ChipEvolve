# Agentic EDA 施工状态

## 最新状态：A19–A21，2026-10-16

当前以根 `TASKS.md` 和 A19/A20/A21 三份报告为准。Flow、两个 Code 和第三方 ECO 已有本机统一 EF/数据交付及真实专业运行；JPEG新增显式完整旋钮来源的基线复制/SDK/冻结环境资格，尚无JPEG专业搜索。Query已从原日志/网表/对象差分查到GCD两次Vt替换和一次buffer移除。四个固定功耗方法与两组控制交付、四个优化结果完整验证；GCD低功耗选择0.884755515mW，面积/余量取舍明确，原DPL保留；AES仍保留34.931797534mW的A9Goal。

本轮三次物理阶段同时租约失联，有界恢复均通过，唯一根因未修；不能宣称单机稳定性全部完成。相同固定源码仍重复构建、团队全面优于最强单项尚未证明。正式同预算长轮次和新Code搜索未启动，协议仍为 `FORMAL_EXPERIMENT_PROTOCOL_20261016.md` 草案。EF/DF服务和九模块版本未改，A17干净DF/只读历史库、原用户修改保留。下一片先解决失联稳定性，再削减重复成本并开展按瓶颈分支的PPA实验。

以下为历史切片过程，日期和验收边界保持原意；原 U4 AES 未正常收尾、失败和无晋升记录不因后续成功被改写。

## U3 工程验收通过，业务确认待老板：2026-10-13

DPLEvolve 已迁移共同源码，并接入共享构建、私有候选 relink、完整原生评价三个 EF 入口。真实 GCD 三基线、原生 Teacher/Student 新源码演化及固定来源独立编译重放通过；138 项测试、89 项工程核查通过。候选/重放 HPWL 均 3093.5 µm，比同环境 Diamond 3206.7 µm 减少 3.53%；运行 0.768/1.008 s，低于 1.176 s 原生预算。相对 framework 最大位移增加 38.37%，前段 producer 零收益，不宣称完整 PPA 已改善。

构建使用私有副本承接上游生成文件，冻结源码保持原身份。保留全部 21 个 EF run、三次候选评价、模型计数、来源与用户修改；13 成功、6 次准备构建失败、2 次旧兼容构建取消。报告见 `U3_DPLEVOLVE_COMMON_TOOLCHAIN_REPORT_20261013.md`，最终回执 `var/code-agent/u3-dplevolve-common-20261013/u3-acceptance.json`。停止于 U3 边界；U4、GoalEvolve 统一执行、统一数据交接、完整协同及收益测量尚未完成。

## 本轮最新结论：2026-10-12

U2 共同工具环境 Flow 完整工程验收通过，业务确认待老板。冻结 Flow `9bdb417`、Toolkit `e7e77c6`，保留原生 A2 算法与专业脚本；AES 两轮六候选、四个真实恢复窗口、42 个 EF run 和 12 个 SDK 评价快照全部通过，180 项工程核查、六份面积来源核对与 136 项对应/相关回归通过。固定新 CP0=0.81 ns；最佳可行 \|TNS\| 1.76→1.47 ns，约减少 16.48%，功耗报告值 0.352 W、芯片面积 38,927.3 µm² 不增加。该结果是单实验观测，不是平台公平收益。

模型 17 次请求、16 次成功，一次 routing selection CLI 失败后原生默认回退；记录完整，失败用量未知，已知成功用量 281,540 token，不作精确成本对比。首轮审计缺 CTS 模型配置/选择审阅条目，补齐真实回复/日志及数值参数原始来源后通过，初次回执保留。旧共享文件增强类型检查的五项既有问题与 Git 基线一致，新增代码增强检查通过，未顺手改旧逻辑。运行证据 `var/flow-agent/u2-common-20261012/u2-acceptance.json`，报告 `U2_FLOW_COMMON_TOOLCHAIN_REPORT_20261012.md`；实验服务已停止，原有用户修改保持。两个 Code 迁移/接入和协同工作流仍未交付；本切片收尾后暂停等老板业务复核。

U1 共同工具链资格验证工程验收通过，业务确认待老板。完整固定源码与递归依赖在选定镜像内通过 EF 构建成功；115 MB 实际 binary 加载真实 GCD 产物、检查合法性/时序并写出 byte-identical ODB。原厂 GCD RTL→GDS、OpenDB/STA 导出及最终指标/单位的公共适配导入全部通过；SDK 返回 5,682 实体、11,805 关系、76 路径/1,882 点和 14 项单位明确的指标，来源与原报告值核对通过。六个 EF run 均成功；数据收尾只新增元数据转换，没有重复四项已完成的任务。

老板要求按任务规模分配资源，单构建已调整为 64 GiB / 2048 进程、8 编译线程及单 LTO worker；成功构建进程树 RSS 峰值约 31.8 GiB、33 进程。构建检查点明确绑定原失败 EF run、源码、镜像和编译参数；原失败与缺指标/单位的初次审计保留。35 项新增检查、137 项相关回归通过，另有一项条件跳过；业务代码/公共契约和用户原有修改未动。

报告 `U1_COMMON_TOOLCHAIN_REPORT_20261012.md`；最终回执 `var/toolchains/common-u1-20261012-retry6/u1-acceptance.json`；数据收尾 `unit-completion-retry1-runtime.json` 及对应 SDK evidence。U1 / U2 工程收尾已完成，两个 Code、所有执行/数据入口及协同工作流的缺口保持。下文保留本轮来源审计和历史过程。

## 来源审计时的状态（历史，2026-10-12）

老板已确认三专业项目后续采用本机 10 月 ORFS SIF `8e6ee7…` 为共同基础环境。官方 Jenkins master/1642 的 checkout、OpenROAD 子模块及镜像 digest 发布记录已核实 ORFS `5105b0a77` / OpenROAD `27288f5c90`；2,407 个镜像保留文件与对应源码完全一致，13 个迁移关键文件 blob 核对通过，三个指定历史 ODB 单向读取成功。来源审计已完成；尚未切换运行环境、构建共同源码或移植专业补丁。

DPLEvolve 基础 patch 在新版 `src/CMakeLists.txt`、`src/Main.cc`、`src/OpenRoad.cc` 需适配，ORFS overlay 也不能原样应用；GoalEvolve 需要追踪并迁移定制 `repair_power` 及必要 policy/move/rmp/STA 依赖，不覆盖新版整目录。报告见 `COMMON_TOOLCHAIN_AUDIT_20261012.md`，具体 U1 文件/数据流/接口/验证/影响面及 U2–U5 路线见 `COMMON_TOOLCHAIN_PLAN_20261012.md`。U1 已授权并进入实现；当前 Git 基线 `4163504`（已发布 ChipEvolve），分支 `u1-common-toolchain-20261012`、既有 evaluation 用户修改保留。

L1/L2 的实测成果与 L3 的未完成项保持如下事实。L3 的本机 Codex 登录适配仍待具体入口确认，未启动 AE-3，九项上游测试失败未解决；旧六小时预算已过期，本轮没有重置。共同版本审计不等于原生复现、统一执行/数据接入或协同 workflow 完成。

## 原生复现检查点：2026-10-11

L3 / GoalEvolve 计划已获老板确认，环境/AE-1/模拟 smoke/AST 初始化/真实 AES AE-2 重放/p0 本机基线冻结通过。p0 为 |TNS| 12.37 ns、动态功耗 427,394,076,214.0958 pW、漏电功耗 95,383,300.50418 pW。未启动 AE-3；模型入口待老板选择，未修改上游仍有九项历史资产缺失测试失败，因此 L3 尚未通过全部门禁。报告 `L3_GOALEVOLVE_REPORT_20261011.md`；统一执行和数据接入仍为 L4/L6，实施分支 `l3-goalevolve-native-20261011`。

P3 / L1 完整真实工程验收通过，业务确认待老板；当前汇报为 `admin/P3_SLICE_REPORT_20261011.md`，完整回执为 `var/flow-agent/p3-platform-campaign-20261011-retry3/p3-acceptance.json`。Flow 冻结源码 `a90bd07`，本机 AES 两轮六候选全部完成，18 项物理阶段任务、12 项评价和 12 项导出共 42 个 run 均成功，四个实际中断窗口、原任务/产物/模型不重复、18 项真实参数消费和 12 项 SDK 数值/条件/来源检查通过，源码与安装环境未变。

本次固定 CP0=0.792 ns、功耗限制 0.400 W。基准 TNS=-4.36 ns，最优可行为第二轮 slot 1 的 -4.11 ns/0.400 W，|TNS| 单次改善约 5.73%。第二轮 slot 2 为 -4.41 ns/0.402 W，功耗超限；slot 3 为 -4.43 ns/0.400 W，未改善。17 次真实内部模型调用均成功，账本记录 305,632 token；此数字不含主 Codex 对话或前期失败/调试成本，不当作端到端成本对照。原生模型数值回退和未入选的直接提案均保留，公平平台收益待 L8。

大物理产物通过现有 materialize_artifact 的本机文件复制/hash 路径交接，HTTP 传少量管理与定位信息。真实 17.6 MB 包合计约 0.026 秒（已有缓存）。完整 SDK 收尾以 API-only 方式重开本实验原 EF/DF 状态，12 个快照验证通过且 42 个 run 身份/状态不变，无 EDA 重跑；一次查询分页参数错误与 SDK 回执尚未齐全的初次审计均保留。正式 Flow 48 项检查、新收尾脚本静态检查、9 项恢复/资源/进程检查和 4 项数据来源检查通过。

L2 / DPLEvolve 原生复现工程验收通过，业务确认待老板；报告为 `admin/L2_DPLEVOLVE_REPORT_20261011.md`，回执为 `var/code-agent/l2-dplevolve-20261011/l2-acceptance.json`。正式独立仓库固定上游 `96d8c613` 且源码干净；独立 ORFS/OpenROAD 按原项目 anchor 准备，共享 core 真实构建成功，GCD / Nangate45 的 RTL→布局快照、三条合法原生基线、prompt/workspace smoke、一轮 Teacher/Student/review 和新源码候选完成。原生轮次 15:37:02–15:54:02 正常结束；控制/基线未变，37 项总核查和六项固定源码重放对照通过，新增及既有根回归共 25 项、数据回归四项通过。

本轮候选源码 `8a7a417` 相对准确 diamond 起点真正修改九个算法文件，固定 candidate/rejected refs 并保留干净工作树；独立 clone、全新私有构建及明确 binary 重放产生相同的 2941.7 µm HPWL、阶段值、位移和合法性，原生时间 0.660 s。相对 OpenROAD 默认 2969.1 µm 少 0.923%，但仍未超过项目自带框架 2941.1 µm，最大位移 15.377 µm 比默认 8.989 µm 高约 71.1%，Student 拒绝晋升、Teacher 确认可运行并保留研究证据。本次不是最终布线 PPA 或平台收益。三项模型操作累计输入 4,234,420、输出 39,522 token，其中输入缓存 3,947,520，不含主对话或前期失败成本。首次 Python/yaml 和合法性审计问题均保留现场并修正。DPLEvolve / GoalEvolve 尚未接入统一平台；下一切片 L3 / GoalEvolve 原生复现，L4 再收口统一执行。以下内容保留为历史过程，不覆盖上述最终回执。

## 历史执行过程

更新日期：2026-10-11。老板已明确同意恢复本机施工：Query 增强成熟 Codex 的领域能力；先跑通本机实验和三项目协同，教学/新用户安装/论文交付暂缓。本轮执行 P3 / L1：首次任务拒绝是 8 核额度再乘默认 60%，未启动物理实验；修正本实验 platform-fraction=1.0 后，retry1 真正受理并运行 placement，但第一个中断后恢复失败，验收脚本漏停 GNU timeout 的子进程组，残留 publisher 持锁。两次失败保留；retry1 的 EF placement 已成功，残留 publisher 按专有运行路径核实后清理，旧服务未动。修复只涉及验收 Controller 会话的停止，不改 Flow 算法和公共接口；静态检查、资源 API 与真实进程锁回归通过，Flow 原有 47 项检查通过。检查记录见 var/flow-agent/p3-local-checks-20261011-control/receipt.json。

最新：retry2 的三个真实布局任务成功，但 Flow 通过整包下载取回 17.6–18.0 MB 产物时被 4 MiB 响应上限拒绝，未进入 DRP，整个实验失败。正式 Flow `a90bd07` 已改用现有公共 materialize_artifact 接口，保留本机定位/复制、远程分块和 hash 验证；48 项检查通过，真实 17,579,577 字节产物取回验证通过，证据见 var/flow-agent/p3-large-artifact-check-20261011。新建 retry3 实验目录，完整 P3 仍待验收。老板已再次同意按施工计划继续，当前仅修复并验证 L1，不跨切片修改 Code。

retry2 完整物理实验已启动，第一个实际中断窗口恢复通过：丢提交回执的请求恢复后接回同一 EF run，实际 placement 成功，公共 runs 接口确认该 slot/stage 仅有一个 run，原 Controller 会话无残留 publisher。证据见 var/flow-agent/p3-platform-campaign-20261011-retry2/first-window-resume-review.json。记录时后续候选仍在运行；其余三个窗口、两轮正常结束、全量反馈与来源仍待核实，P3 未验收。即时状态见该目录 receipt.json / supervisor.log / campaign.log。后续计划见 admin/LOCAL_EXECUTION_PLAN_20261011.md。根目录 PROJECT.md / ARCHITECTURE.md / TASKS.md 同步业务范围；后文早期记录保留为历史。

## 最新验收与运行

P2 的真实 place→CTS→route_finish→eval_final 均成功，TNS=-4.36 ns/power=0.400 W 与原生基准报告值一致。真实 AES routing 在并发列表读取下取消：相关原始 PID 全部消失约 0.127 秒，终态约 0.228 秒，资源归零。初次数据验收的 `KeyError: data` 是验收程序误把 POST import 的直接结果当作 GET envelope；原失败 receipt 保留。

修复后 `continue_a2_data_acceptance.py` 以 API-only 方式打开本次独立 EF 状态，复用已经注册的物理/评价/实体/指标快照产物，在新的独立 DF 状态完成并发重复导入、两次重启回执与 Data Interface SDK 查询。执行模块源码/安装依赖与原物理实验相同；验收脚本修复前后 hash 单独声明。EF run_id 集合完全不变，没有重跑物理或评价任务。最终验收见 `var/flow-agent/p2-a2-stage-20261010/p2-acceptance.json` 和 `var/flow-agent/p2-data-acceptance-20261010/receipt.json`，原失败记录不覆盖。

P3 已准备薄 leaf adapter：公共 EF wheel/HTTP、原生候选 identity/实际 DRP donor、ODB/SDC hash、持久任务请求、丢提交回执时幂等重取、注册产物投影与原生评价 log。七个边界检查通过；模拟任务只算工程检查，不是实际 P3 验收。原生模式保留，尚未实现/验收整个 campaign 恢复，不能把单叶子可重取当作完整续跑。

retry2 于北京时间 17:27:48 正常退出 0，源码未变、产物采集退出 0。两轮各三候选均完成，36 个最终文件保存并校验；18 条参数消费观测全部匹配，最终 ODB 的实际 routing adjustment 与归档配置一致。固定 CP0=0.792 ns，基准 TNS=-4.36 ns/power=0.400 W；最优可行观测为第二轮 slot 1，TNS=-4.11 ns/power=0.400 W，|TNS| 降低约 5.73%。单次观测不代表平台公平收益已经证明。

17 次真实模型请求，16 成功、1 inspection 失败并回退。账本完整，已知用量 275,660 token；失败用量未知，精确总成本仍不可知。两次完整实验与失败记录均保留。

初次收尾审计仅 `round_2_place_llm_parameters` 未通过，保存在 `p1-acceptance-initial-stage-origin.json`。真实模型选择 kmeans/零质量权重/零 uncertainty，数值采样候选胜出，直接 LLM 提案进入候选池但未入选。源码、四份真实响应、运行日志、生成参数与后续工具消费均已审阅；验收改为验证真实模型决策有效，并继续分别报告直接提案是否入选。缺审阅或 decision hash 不符均拒绝，见 `stage-selection-audit-verification.json`。最终 `p1-acceptance.json` 所有检查通过，没有修改运行算法或重写候选来源。

原自动衔接在初次审计失败处停止，其 `p1-p2-handoff.json` 保留为失败记录。P1 复审通过后，北京时间 18:43:50 已直接启动 `var/flow-agent/p2-a2-stage-20261010`，当前为真实布局任务；实际 gateway/run 身份与请求见该目录 `receipt.json`。不再运行衔接脚本，不重复启动 P2。

## 当前工作

已封存本机 A2 上游提交、全部已跟踪修改、未跟踪源码、工具与安装依赖。正式 Flow 基线提交为 `a4f72ce51de6a4565ad85333b2fe6cbe1936aecd`，独立环境检查通过，27 项 Flow 回归通过。

首次实验的失败回执、原始日志和 [验收记录](/home/wjyuan/projects/eda-development/var/flow-agent/p1-native-20261010/p1-acceptance.json) 均已保留。第一轮基准候选完成全流程，但布线整批 20 分钟用尽，最终有效候选为 1/3，原生关卡要求至少 2；退出码 1，第二轮未运行，源码 hash 未变。原目录不作为施工目录。

完整重试使用同一封存源码、同一算法与模型条件，将每候选线程从 2 调到 8、整批阶段时限从 20 分钟调到 90 分钟；两轮三候选、物理并发一、三小时总预算保持一致。当前命令、进程和终态见 [重试 receipt](/home/wjyuan/projects/eda-development/var/flow-agent/p1-native-20261010-retry1/receipt.json)，输出见同目录 `campaign.log`。封存证据仍引用首次目录 `baseline/manifest.json`。

Data Foundation 已增加指定产物的持久化导入回执、失败记录与重试、批量翻页，并通过 375 项检查，包括真实 HTTP 并发重复导入。证据为运行目录 `data-foundation-check-http.log`。未改动旧数据库或服务。

EF 新状态的默认盘/内存盘配对测量已完成。150 条记录写入分别约 77.53 秒与 0.016 秒；无并发写入时列表查询约 0.5 至 3.6 毫秒。新原生 OpenROAD 取消在两个存储条件下各测三次，进程消失与本地终态均低于五秒；这不是此前失败场景的 HTTP 复测，不据此关闭历史取消问题。

EF 列表改造已通过完整检查：366 passed，1 skipped；提交 `786bab5`。同规模默认盘筛选查询由 153 次 SQL 减到一次，测得约 3.35 毫秒降至 0.154 毫秒。另一次记录写入耗时变化受机器负载影响，不能归因于只读列表改造。

DF 可靠导入提交为 `95affc8`。已有几何查询和 pending STA 投影等用户修改保留，未纳入本次提交；当前检查覆盖包含这些既有修改的工作树，其补丁和安装状态存于运行目录。Flow 开发规则提交为 `20755ce`，本次物理实验仍固定使用 `a4f72ce` 源码副本。

## P1 当前已核实的运行事实

首次失败实验中，第一轮三候选的布局与 CTS 均成功。两次真实模型调用共输入 41,304、输出 244 token，CTS 和布线参数实际进入配置；run 2 继承 run 3 布局，run 3 继承 run 2 CTS。基准最终 CP0=0.792 ns，TNS=-4.36 ns，功耗 0.4 W；其 ODB/DEF/V/SPEF/SDC/GDS 均保留。没有完整第二轮或收益证据，不能用这次部分结果代替重试验收。

原生备份只保存 SDC，下一轮会清理上一轮物理产物。独立 `capture_native_iterations.py --run-root ...` 在原生备份边界采集每轮最终 ODB/DEF/V/SPEF/SDC/GDS 到运行根目录 `iteration-results`，逐文件校验 hash；没有修改运行中的算法源码。重试 supervisor 自动启动采集器并记录其身份与退出码。

默认盘真实 HTTP/worker 路径已复现取消延迟：三次接口终态耗时约 26.93、27.11、14.23 秒，进程消失约 1.77、9.37、6.05 秒。改用 SQLite WAL、保留 FULL 同步强度后，同一脚本三次终态约 2.75、1.49、0.14 秒，原始进程树消失均小于一秒。证据在首次目录 `http-cancel-disk.json`、`http-cancel-wal.json`；独立内存盘对照也保留。完整 EF 检查 368 passed、1 skipped，mypy 41 文件通过，见 `ef-check-wal.log`。这验证了真实 OpenROAD 初始化与子进程取消；P2 仍需真实设计阶段验收，不把等待脚本当作完整物理任务。

EF WAL 修复提交为 `d0302c1`。真实 HTTP 列表验收已提交 150 条任务，以 API-only 模式查询三页各 50 条，无重复或遗漏，第四页和不存在项目均为空，见首次目录 `http-listing.json`。这是分页验收，不是物理设计实验。写入耗时受当时负载影响，不据此归因总体性能收益。

Toolkits 的阶段接口已准备并通过 48 项检查；实际 AES 检查点在原生 Make 上的外层和叶子 dry-run 均只计划 CTS，不重跑上游。证据为重试目录 `toolkits-stage-preparation-check.log` 和 `var/flow-agent/p2-interface-preparation/cts-inputs/dry-run-receipt.json`。没有改动 A2 dispatch，没有执行正式 EF 物理阶段，也没有完成 P2 业务验收。

完整重试第一轮已完成 3/3 最终物理流程；独立采集器保存 18 个最终产物。基准 TNS=-4.36 ns、power=0.4 W，另两个候选均为 TNS=-8.16 ns、power=0.38 W；首轮没有时序改善。第二轮已开始真实布局。跨轮七次模型响应已逐项审阅：模型的 48% 利用率、0.18 密度调整提案通过选池并进入第二个候选；三条 CSV 事件、输入 hash 与生成配置相符。证据为重试目录 `model-decision-review.json` 和 `decision-review-evidence/`。原生交互式 GPR 分支因少于四个历史样本跳过，候选预测在少量样本下平坦；不能宣称该分支实测通过。最终 P1 验收仍等待第二轮及正常结束。

P2 验收入口已补齐真实 AES 布线取消与实体数据导入：阶段链通过后，用原生 CTS 产物启动真实全局布线，在并发列表读取下核对原始进程身份、五秒取消和资源归还；再通过 Toolkit 从该次最终 ODB 导出快照，用新的 DF 状态验证并发重复导入与服务重启后的回执。此入口尚未运行，不将准备工作计作业务能力完成。

## 恢复入口

2026-10-10 08:49 UTC 续接：retry2 第一轮 3/3 完成并保存 18 个最终产物；三个候选 signed TNS 分别 -4.36/-4.15/-4.49 ns，功耗 0.400/0.401/0.401 W，后两项超限，尚无可行改善。第二轮布局正在运行，不启动重复实验。

当前实验的跨轮模型审阅已签署 `model-decision-review.json`，与 retry1 分开：六次成功响应、一次 inspection 失败；默认四 cluster/0.3 配置由源码与运行日志核实。Matérn/minmax/EI/0.55 与 elitist/零 uncertainty 已进入原生流程；模型的 48% utilization、0.18 density、0.48 floorplan pin 提案精确对应第二轮 slot 2。三个 CSV 事件、配置与 SDC 的全部数字均已核对。第三项为 quota-forced full probe。ReAct GPR 因历史不足跳过；Critic/TextGrad 更新后续指令，不能解释为本批选择者。

`accept_native_campaign.py` 现在按原生 `llm_usage.build_summary` 只读重算并核对整个账本：每次调用必须有唯一、身份一致的开始和终态，成功用量必须一致，无 pending。已记录失败且成本未知时，执行账本可以完整，精确总成本仍不可知。审计输出分别保留 `model_ledger_audit` 与 `model_cost_complete`，成本缺口不得用于 P6 精确成本收益比较。五个验证案例覆盖记录失败、篡改总量、缺终态、重复终态和跨 campaign 混入；证据在 `ledger-audit-verification.json`，其合成终态仅用于审计规则验证，不是最终实验验收。

Toolkits 最新 `39f48a4` 与 DF `b29e5a9` 保存 CP0 的真实 WNS 名称，避免把 clipped WNS 当作可为正的 WS；49/376 项检查通过。P2 准备完成但未执行；P1 完整收尾、最终 ODB 参数消费与 canonical 验收通过后直接运行真实阶段链。

retry1 于 07:31 UTC 正常结束：退出码 0、source_changed=[]、capture_exit_code=0，两轮各 18 个最终物理产物。17 次真实模型调用，309,360 token。最终基准和可行最优 TNS=-4.36 ns、power=0.4 W；第二轮第三候选 TNS=-3.15 ns 但 power=0.462 W，超功耗，不计改善。`p1-acceptance.json` 仅参数物理消费及其证据门槛不通过，因此没有启动 P2。

真实接口验证证据为 `var/flow-agent/p1-routing-probe-20261010/receipt.json`：加载本次真实 AES ODB，四次 OpenROAD capacity setter 均返回 0，两个阶段分别使用独立提案。新冻结基线为 `var/flow-agent/p1-routing-baseline-20261010`，修复实验为 `var/flow-agent/p1-native-20261010-retry2`；supervisor 使用同一显式 baseline。首个真实 floorplan 日志已出现 `scope=floorplan pin=0.5 above=0.25`，其余阶段与最终完整验收仍待运行。

`capture_native_decisions.py` 正在等待第二轮配置生成边界，保存模型输入批次、三份配置/SDC 与 lifecycle 到新实验 `decision-review-evidence`，供人工核实；不会自动签署模型决策审阅。修复实验结束并采集完后运行 `review_native_consumption.py` 核对两轮实际工具日志与继承配置，再审阅真实模型决策、完成 P1 审计、推进 P2。

接入准备已进一步覆盖真实评价回流：Toolkits 提交 `190f5e7` 在完整 CP0 评价成功后输出 `a2-evaluation.json`，包含实际 signed TNS/WNS、power、单位、固定时钟与库条件、SPEF 模式及源日志 hash；缺功耗等失败不输出成功反馈。48 项 Toolkits 检查通过。P2 入口会通过既有 ORFS metadata adapter 生成可导入快照，使用独立新 DF 状态，并以 Data Interface 自己的已安装 SDK 验证重启前后相同指标和源字节。相关脚本已通过 lint/compile/CLI 检查，尚未作为真实接入验收执行，不据此标记 P2/P3 完成。

Toolkits `83301d2` 与 DF `077b47e` 进一步保存实际 evaluator 的来源和评价条件到指标行，避免 CP0 评价被误标为常规 ORFS 阶段报告。49 项 Toolkits、376 项 DF 检查通过；DF 原有六项用户修改保留，未纳入提交。SDK 验收要求指标条件与实际评价 metadata 完全一致，并且证据解析到注册的原始 metadata artifact 与 hash。首次新增 fixture 检查暴露证据规范化及缺失 stage，已修正 fixture，原失败日志均保留于 `p2-interface-preparation/feedback-context-data-check*.log`；不是放宽业务验收。

最新物理消费审计在重试目录 `parameter-consumption-review.json`：生成的 FLOORPLAN_PIN/ABOVE 与 PIN/ABOVE 参数未被 Nangate45 默认脚本消费，默认实际容量固定为 0.5/0.25；CTS 两项参数确实被消费。正式 Flow 提交 `57be217` 补充独立 floorplan 和 post-CTS routing hook，保持原平台基准容量不变，29 项检查通过。Tcl stub 检查只证明参数接线，真实工具 setter 与修复后的两轮物理实验仍待验证。不得改动当前运行副本或从不同源码实验拼接验收。

修复后的源码基线通过 `admin/freeze_native_revision.py` 冻结原始归档与 Git delta；启动新实验时 `prepare` 和 `supervise` 均显式指定新 `--baseline`。当前实验的续接监督器只有 P1 审计通过才启动 P2，因消费门槛不通过，预期不会启动正式接入。

读取 [施工目标](PROJECT_CONTRACT.md)、[版本与接入关系](INTEGRATION_MAP.md) 和 [运行手册](RUNBOOK.md)，再查看运行 receipt 与原生 campaign 状态。不得仅凭聊天内容把阶段标记完成。

第一关仍待验收：同一实验的真实模型调用、多轮物理流程与正常结束共同成立后才推进正式接入。恢复时先读实时 receipt、原生账本与 capture.log；本页是索引，不能覆盖运行记录的最新状态。

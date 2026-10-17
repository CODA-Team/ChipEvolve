# A25：原 Goal 功耗接力的执行保真核查

AES 的既有 DPL 输入，经同一冻结 Goal Student4 源码及原功耗配方，分别直接运行和通过原专业 EF 接口运行，两侧实际优化动作、关键网表/数据库及最终七项 PPA 完全一致；EF→DF→公开 SDK 的七项事实也一致。本次补齐固定专业动作的执行保真证据，没有新 Teacher/Student 搜索、源码构建或结果采用，不能代替 JPEG 健康 Code 轮次及正式公平对照。

## 实际核查

- 复用原 A21 AES 接力：DPL 生产者 `run-ad77204de2394387a2a9a11f634301dc`；原 Goal Student4 源码身份 `f20120a3463c7d3dd4937000ad8dfb59558cc1b034d3d3c0b552db236fd2acee`。701 份专业源码、46 项原输入和 120 份冻结控制器文件哈希通过。
- 保留原 `repair_design`、`repair_power -phase early_forced_reclaim -proportion 80`、显式 Diamond、线程、库和 SDC。仅重定位输出；历史输入目录在专业容器内只读。物理请求实际绑定原 DPL 的数据底座上下文、原目标和源码/二进制。
- 两侧均为 145 次尝试、18 次接受降尺寸，原生完整动作统计一致；`pre_repair.v`、`post_repair_power.v`、`post_route.v`、`post_route.odb` 四份文件逐字节一致。
- 两侧各自完成完整 DRT/RCX、共同 FF 测量。平台原专业物理执行、完整布线、共同测量及 ORFS 事实发布共四项 EF 任务，全部成功且各一次 attempt；最终 SDK 七数值一致，DRC/布局/电气违例为零。独立核查 59 份产物/证据哈希，26 份用户文件保持。

| 最终事实 | 直接与 EF 两侧同值，也等于原 A21 结果 |
|---|---:|
| 功耗 | 34.947216511 mW |
| 单元面积 | 1254.13 µm² |
| core / die 面积 | 1941.63 / 2321.51 µm² |
| setup 最差 slack | 0.201938 ns |
| setup / hold TNS | 0 / 0 ns |

面积从原输入 1256.04 降到 1254.13，修复原 1255.75 上限违例；最终功耗却比原输入增加 98.843128 µW。历史匹配的无 repair 控制为 34.975331277 mW，相对该控制，repair 组减少 28.114766 µW。该历史控制本次没有重跑，分离的是整组 repair 及其后续物理实现影响，不把差值分摊到每个动作或外推所有设计。保留原 A9 Goal 的 34.931797534 mW，不以最后一棒覆盖更好的合法分支。

## 成本和限制

两侧串行准备合计墙钟 684.495 秒，新增模型调用为零。直接侧三条物理命令已回收后代 CPU 1743.552 秒；平台四项托管 attempt CPU 1676.45 秒。主 Codex 推理、前端及独立 EF/DF 服务 CPU 不在这两个观测范围内；RUSAGE_CHILDREN 的 maxrss 为累积高水位。共享 JPEG 正在运行，不能据此计算正式效率比。

第一次独立核查将平台发布的 `metrics/metric_context` 包装误读为直接侧的平铺指标，报 KeyError；原错误日志和核查脚本保留。按已存在的数据格式读取后通过，未改 DF/接口、原数据或重跑模型/EDA。本次没有新的完整功能证明，不授权新采用；完整 Teacher/Student 推理与源码构建仍由后续健康轮次验证。

运行证据在 `var/business/a25-formal-preparation-20261017/fixed-aes-professional-r1/`：`independent-acceptance.json`、`evidence-hashes.json`、`managed-runs.json`、`sdk-final-facts.json` 及两侧原始日志。成本续接 `preparation-costs-r8.json`，此前失败和未知项保留。

## 后续队列

已启动 `serial-calibration-continuation-r1` 等待队列，PID 1474920，目前仅等待原 JPEG，未更新服务或启动新的搜索。45 份文件指纹固定，按以下顺序串行执行：

1. 原 JPEG 完整 Flow/候选交付成功、原前端关闭且公开 EF 队列和 attempt 空闲后，仅原位更新已验证 Gateway wheel。
2. 实际生产监听/50 客户端 150 上传及历史 GCD/JPEG/AES SDK 核查通过。
3. JPEG DPL 一轮三 Student、Goal 一轮四 Student；各用已资格验证的 r6 配置、同一原来源/上下文、原算法和目标，给准备/构建/搜索共同 12 小时监督预算。没有并发完整 Flow 或双 Code 构建。
4. 以新 r2 配置运行 GCD 原两轮×50、恢复原 utilization 20–99 的完整搜索，预算 72000 秒；旧窄范围失败与 65/80 控制保留。

任一步失败或交付 pending 即保留原 key 并转入同阶段诊断，不自动重跑搜索或跳过验收。该队列只执行已批准的 A24/A25 校准，不选择赢家、不自动采用，也不冻结正式预算；Code 真正接力、完整证明/重放、A25 冻结和 A26–A28 仍需实际完成。

本轮没有修改产品、专业模块或服务源码；新增验证脚本和运行数据仅在 var。原 451 项根回归已经通过，未因纯实测/文档重复执行。队列语法、45 项输入指纹及无动作 dry-run 通过；工程核查与老板业务验收分开。

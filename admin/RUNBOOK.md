# Agentic EDA 施工运行手册

正式源码在工作区各独立仓库。当前阶段为 P1，首次运行 `var/flow-agent/p1-native-20261010` 已失败并保留；当前完整重试为 `var/flow-agent/p1-native-20261010-retry1`。实际命令、进程身份、状态和退出码由各自目录的 receipt 保存。

## 启动与观察

基线准备程序为 `python admin/flow_native_baseline.py prepare`，只接受不存在的目标目录。本次准备已完成，不能再次执行。实际启动使用 `python admin/flow_native_baseline.py supervise`，已有 receipt 时拒绝重复启动。

本次命令：`./run.sh -p nangate45 -d aes -o TNS_EVAL -i 2 -r 3 -k 1 -s elitist -A -P -F --seed 42 --cpus 6 --max-concurrent-runs 1 -t 20m`。supervisor 使用独立环境、官方 Codex transport 和三小时总预算，运行结束后写入退出码及源码 hash 变化。

只在封存后的独立运行副本执行 A2；不借用旧 cp0、backup_dir 或 optimization_state。激活正式 Flow 的独立虚拟环境后启动原生入口。日志保存在运行根目录，原生数据仍保持 A2 要求的相对目录关系。

运行前核对同目录 receipt。已有进程仍活跃时不重复启动，也不编辑运行副本的脚本。观察 campaign 日志、原生使用账本和每轮 result_dump，不能仅凭 shell 存活判断任务成功。

## 停止与恢复

P1 原生 A2 尚不支持同 campaign 续跑。中断后保留该实验和退出原因；需要重试时使用新独立运行目录。`-F` 归档重开不是续跑。

仅停止 receipt 记录且仍符合原始进程身份的本次实验进程组。不要按 OpenROAD 名称批量杀进程，也不要重启旧 EF/DF 服务。P3 完成后再登记同 campaign 的显式恢复命令。

完整重试由 `admin/run_native_campaign.py` 创建新目录、检出同一封存提交并核对源码 hash。当前重试已启动，不能再次启动。通用入口分别为 `prepare --run-root <新目录>` 与 `supervise --run-root <已准备目录> --threads 8 --stage-timeout 90m`，执行前先核对 receipt 和进程。supervisor 自动启动外部产物采集器、限制三小时总预算并记录双方退出状态。

EF 新版本使用 SQLite WAL，保持 FULL 持久化。在线保存数据库应使用 SQLite backup 接口；离线迁移需先关闭使用该状态的所有连接，并连同对象目录迁移。不能只复制运行中的 `runtime.db` 主文件而遗漏 WAL。此次只操作新测试状态，未切换或重启旧服务。

## 验收与交接

完整实验结束后，使用 `admin/accept_native_campaign.py --run-root <实验目录>` 审计同一个 campaign。审计复用原生 canonical 检查，核对模型账本、两轮实际 CSV、检查点继承、预测排序、固定 CP0 和成功候选的全部最终产物。候选失败按原生关卡处理并明确列出；不新增要求所有搜索候选必然成功的条件。跨轮模型输出是否实际影响下一批，先形成同目录 `model-decision-review.json`，再冻结 P1 验收。

P1 通过后，用 `dev.py execution-foundation python ../admin/run_a2_stage_acceptance.py --native-run <已验收目录> --state <新目录>` 执行 P2 的真实 AES 阶段链。入口拒绝未验收的 native campaign；先保存请求，再通过 HTTP 提交、等待和传递产物。每段保留 EF run、配置和命令回执，核对继承文件 hash、实际执行阶段和完整最终产物。此入口是阶段接点验收，同 campaign 续跑在 P3 实现。

核对源码 hash 未变、正常退出、两轮真实结果、固定 CP0 与功耗、模型决策进入配置、第二轮预测排序、候选淘汰及来源。保存失败和 fallback。通过后更新 STATUS，进入 P2，不将物理流程成功写成收益已证明。

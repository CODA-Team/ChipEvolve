# Agentic EDA 施工运行手册

正式源码在工作区各独立仓库。当前阶段为 P1，运行根目录为 `var/flow-agent/p1-native-20261010`。实际命令、进程身份、状态和退出码由该目录的 receipt 保存。

## 启动与观察

基线准备程序为 `python admin/flow_native_baseline.py prepare`，只接受不存在的目标目录。本次准备已完成，不能再次执行。实际启动使用 `python admin/flow_native_baseline.py supervise`，已有 receipt 时拒绝重复启动。

本次命令：`./run.sh -p nangate45 -d aes -o TNS_EVAL -i 2 -r 3 -k 1 -s elitist -A -P -F --seed 42 --cpus 6 --max-concurrent-runs 1 -t 20m`。supervisor 使用独立环境、官方 Codex transport 和三小时总预算，运行结束后写入退出码及源码 hash 变化。

只在封存后的独立运行副本执行 A2；不借用旧 cp0、backup_dir 或 optimization_state。激活正式 Flow 的独立虚拟环境后启动原生入口。日志保存在运行根目录，原生数据仍保持 A2 要求的相对目录关系。

运行前核对同目录 receipt。已有进程仍活跃时不重复启动，也不编辑运行副本的脚本。观察 campaign 日志、原生使用账本和每轮 result_dump，不能仅凭 shell 存活判断任务成功。

## 停止与恢复

P1 原生 A2 尚不支持同 campaign 续跑。中断后保留该实验和退出原因；需要重试时使用新独立运行目录。`-F` 归档重开不是续跑。

仅停止 receipt 记录且仍符合原始进程身份的本次实验进程组。不要按 OpenROAD 名称批量杀进程，也不要重启旧 EF/DF 服务。P3 完成后再登记同 campaign 的显式恢复命令。

## 验收与交接

核对源码 hash 未变、正常退出、两轮真实结果、固定 CP0 与功耗、模型决策进入配置、第二轮预测排序、候选淘汰及来源。保存失败和 fallback。通过后更新 STATUS，进入 P2，不将物理流程成功写成收益已证明。

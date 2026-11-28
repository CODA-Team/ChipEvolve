# A111 本机 GCD 专业 Agent 验收

本轮从 `engineering/cleanup-b6cfd1d` 的 `826e847` 工作树开始。五个 Agent 的入口、交接条件和运行时说明见 [派发表](../agent/README.md)。本机运行记录在 `var/instances/a111-gcd/`，包括配置、解释器依赖清单、运行日志和交接回执。

## 运行条件

- GCD 使用 Nangate45 typical 库，时钟 500 ps。EF 和 DF 使用 `a111-gcd` 的独立端口、数据库和产物目录。ORFS/OpenROAD 运行在 `orfs-8e6ee7aac233da07.sif`，镜像摘要和测量条件写进每份 `result.json`。
- Flow、DPLEvolve 和 GoalEvolve 分别使用 `envs/flow`、`envs/dpl` 和 `envs/goal`。三套 Python 3.12.13 环境从 wheel 安装，禁用系统 site-packages。对应依赖在 `envs/*.lock`。EF、DF、Query 和 Toolkits 使用本机发布候选 wheel。DF、DI 工作树的其他在途改动参与源码测试，业务运行使用已安装的 DF `0.2.2.dev1` 和 SDK `0.2.3.dev1`。
- DPL 和 Goal 从本轮标准基线 `baseline` 取得父产物。Flow 从本轮单独生成的 `flow-source` 取得带 Flow 参数和 Tcl 依赖的完整 ORFS recipe。两份基线都经过真实布线和 OpenSTA 最终测量。
- 专业运行复用了服务器上已准备的工具镜像、DPL 框架绑定、Goal 编译种子和 checker。独立 Python 环境和新生成的父产物限定了本轮验收范围。公开 clone、工具链准备和外部安装验收属于发布验收。

## 已核验的交接

| 入口 | 实际运行 | 本轮结果 |
| --- | --- | --- |
| `run --capability flow --flow-recipe source --rounds 1 --candidates 3` | 从已注册 ORFS recipe 重建，三条候选跑完布局、CTS、布线和固定 CP0 评估。原生账本记录两次成功的 Codex 参数提案。 | 三条候选均交付结果。两条满足最终目标约束，一条因功耗、核心面积和芯片面积超限被标记为不可行。候选 2 的 setup/hold worst slack 为 38.8594/110.493 ps，route DRC 为 0。运行保留了候选集和原生排名，未执行采用操作。 |
| `run --capability dpl --operation framework` | 原生三条布局基线，使用所选框架的布局继续 CTS 和布线 | 最终 setup/hold worst slack 为 39.6093/110.325 ps，route DRC 为 0。`cts-consumption.json` 记录 CTS 读入 `3_place.odb`，`route_finish-consumption.json` 记录布线读入 `4_cts.odb`。两份回执绑定同一个布局哈希。 |
| `run --capability goal --operation replay` | 原生控制器用已准备、经来源绑定的 OpenROAD 二进制重放，执行原生 checker，再进入公共详细布线和寄生提取 | 原生结构检查 4/4，包括物理单元、宏、I/O 和触发器完整性。最终 setup/hold worst slack 为 39.7702/110.338 ps，route DRC 为 0。`baseline/build.log` 记录二进制复用。`baseline/baseline.json` 记录可选 Sfinal 观测缺少基准 `metrics.csv`。 |

独立核查通过 EF 客户端和 Data Interface SDK 读取已注册的事实产物和导入回执。两份基线、DPL 和 Goal 的 OpenDB、ORFS、OpenSTA 三类快照都能查回对应的测量 run。Flow 每条候选先发布 ORFS 和 OpenSTA 快照，OpenDB 事实在诊断或下游交接需要时导入。核查也比对了 ODB、SDC、SPEF 的实际 SHA-256 和 EF 接收的字节，以及 SDK 返回的 setup worst slack。结果保存在 `verified-delivery.json`。`resume` 取回四个单结果实验的原 run ID，以及 Flow 候选集的三个原 run ID。回执为 `resume-verification.jsonl`。

Flow 候选 2 通过 `diagnose --against` 回到 Query。诊断触发候选的 OpenDB 快照导入，SDK 在原测量 run 下读回了 5,588 个实体。Query 引用两份结果的时序与功耗，确认候选功耗较低，setup 和 hold 裕量略小且均为正。回执见 `flow-return-open-db.json` 和 `flow-return-diagnose.log`。

DPLEvolve 和 GoalEvolve 本轮覆盖原生确定性路径。Teacher/Student 搜索、全新 C++ 构建和论文规模复现仍需各自的验收记录。

核验结束时本轮实例没有活跃任务，独立 EF 和 DF 服务已停止。状态与收尾回执保存在 `final-status.json`、`stop-verification.json` 和 `stopped-status.json`。

## 工程检查

`python3 dev.py all check` 的退出码为 `0`。九个模块和根项目合计 2,562 项通过，另有 71 个 GoalEvolve 子测试通过。EF 跳过一项只适用于无法枚举子进程的主机的测试。日志为 `checks/all.log`。

| 检查范围 | 通过项 |
| --- | ---: |
| Execution Foundation，含架构约束 | 396 |
| Query Agent，含 Ruff、格式、Pyright 和依赖方向 | 228 |
| Data Foundation | 381 |
| Data Interface | 13 |
| Toolkits | 78 |
| Flow Agent | 99 |
| DPLEvolve | 47 |
| GoalEvolve | 482 |
| TimingECOAgent | 67 |
| 根业务回归 `admin/test_*.py` | 771 |

Flow、DPL 和 Goal 的测试也分别在 `envs/` 的新环境里单独执行。整套检查使用各模块自己的 pytest 入口。根业务回归使用现有 `admin/test_*.py`，历史归档和独立消融在途文件留在各自的工作区。

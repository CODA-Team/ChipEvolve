# A19：第三设计来源与复制资格

本片按 `A19_A21_PURPOSEFUL_RELAY_PLAN_20261016.md` 完成有界资格审计，老板业务验收独立。**官方 ASAP7 JPEG encoder 的显式完整旋钮来源通过基线复制资格**，七项 PPA、SDK 和工具/来源身份均核对。原 picorv32 仍未通过；没有把重跑产生的较低功耗算成优化，也没有删除重定时、缩小 Flow 原参数域或修改原约束。

## 第三个可用设计交付

JPEG 使用同一共同工具链、15 份 FF Liberty 和原 545ps 时钟。来源与复制的最终值逐项相同：

| 指标 | 来源与复制的共同值 |
|---|---:|
| 功耗 W | 0.17833724618 |
| 单元面积 µm² | 6734.18 |
| core 面积 µm² | 9048 |
| die 面积 µm² | 9854.14 |
| setup TNS ns | 0 |
| setup 最差 slack ns | 0.0195042 |
| hold TNS ns | 0 |

原约束通过、route DRC 为 0，OpenDB/ORFS/OpenSTA 三类事实经 SDK 读取的设计/run 身份与最终七项指标一致。环境冻结文件为 `runtime/experiments/jpeg/a19-jpeg-environment/environment.json`，登记到本轮 `runtime/local.json` 的 `qualified_environments.jpeg`。

这取得的是**第三设计的来源复制与冻结环境资格**，没有运行 JPEG 的完整 Flow 搜索或两个 Code/ECO 原生搜索；不能把前置资格写成所有专业已在 JPEG 完成优化，也不能把源与复制完全相同写成 PPA 改善。

第一次复制的 route 在 `06:34:07 UTC` 与两次 AES 独立复测同时失联。恢复直接使用已成功 CTS 的注册检查点，只重做失联 route，place/CTS 不重复；新 route 为 `run-467d17c60e024c35a292f9462544e44c`。原失联 `run-0643deaa1472491fad43d61c64673a93` 保留，新结果在 `a19-jpeg-source-control-recovery-r2/`。恢复脚本首次提交因重复绑定 objective 输入被拒绝，未启动 EDA；修正提交绑定后受理，原 `jpeg-recovery.log` 不删除。此处未修改公共契约、原算法或原任务。

有界恢复成功不等于租约故障已修好。本轮没有定位到唯一根因、改 EF 源码或重启服务，正式长实验仍应先解决此稳定性缺口；失联与恢复细节同时见 A21 报告。

## 已完成的来源排查

picorv32 原来源与新复制都完成真实物理流程和事实交付，但七项最终指标不一致：

| 指标 | 原 A16 来源 | A19 完整复制 |
|---|---:|---:|
| 功耗 W | 0.062410965562 | 0.050820667297 |
| 单元面积 µm² | 2490.31 | 2475.89 |
| core 面积 µm² | 3608.99 | 3599.28 |
| die 面积 µm² | 4133.72 | 4111.37 |
| setup TNS ns | −46.8921 | −36.6125 |
| setup WS ns | −0.179504 | −0.203599 |
| hold TNS ns | 0 | 0 |

差异在综合阶段已经出现。五组 EF 综合控制中，复制 RTL 路径、恢复原 RTL 路径、原/新默认配置的综合面积均为 2181.270060µm²，sequential 为 661.0572µm²；隔离运行目录控制为 2183.704920/641.2284µm²。历史 A16 复制的综合面积为 2158.7148µm²，新 A19 完整复制为 2168.67294µm²。恢复 RTL 路径没有恢复历史结果，因此不能把路径变化宣布为唯一根因；不同运行组织下的综合/重定时结果差异仍未定位到唯一机制。

保留全部控制、网表 hash 和原日志，不加入未经工具支持的随机种子参数，也不关闭原重定时以制造同值。picorv32 暂不进入正式可复现优化对照，不能由此说它完全无法运行或不能做其他专业实验。

## UART 与 JPEG 的选择依据

| 设计 | 真实运行与资格边界 |
|---|---|
| 官方 ASAP7 UART | 完整物理与数据通过，功耗 0.0032593468204W、cell 84.6077µm²、setup TNS=0、WS=0.0246979ns。原固定 DIE_AREA/CORE_AREA 下未设置 CORE_UTILIZATION，完整 Flow 参数资格明确拒绝；不虚构一个不起作用的旋钮来通过资格 |
| 官方 ASAP7 JPEG encoder | 登记显式完整旋钮 Yosys 来源；保留原 545ps 时钟、max-delay 分组和 fanout 约束。原厂内置 SYNTH_USE_SYN=1 与本次显式 SYNTH_USE_SYN=0 是不同来源政策，不把这次结果冒称 stock ORFS 默认结果 |

两份 SDC 声明均显式使用 ps 和数值时钟，UART 保留虚拟时钟、20% I/O 延时和 66.270ps latency，JPEG 将原 include 内容展开但保留约束含义。资格按接口所需参数与复制一致性判断，不按谁的 PPA 更好挑设计。

## 可核查资产与工程边界

运行根 `var/business/a19-a21-purposeful-relay-20261016/`：

- `runtime/experiments/picorv32/a19-full-source-control/comparison.json`：原来源与新完整复制七项差异及原约束。
- `synthesis-controls.json`、`synthesis-default-controls.json`、`synthesis-isolated.json`：五组 EF run、综合网表 hash 和实际 synth_stat 路径。
- `uart-declaration.json`、`uart-qualification.log`：约束声明、真实运行及完整参数域拒绝原因。
- `jpeg-declaration.json`、`runtime/experiments/jpeg/a19-jpeg-source/`：来源政策、约束、EF 原始产物及最终设计事实。
- `runtime/experiments/jpeg/a19-jpeg-source-control/`：原复制 place/CTS 成功及首次 route 失联；原证据不改写。
- `runtime/experiments/jpeg/a19-jpeg-source-control-recovery-r2/`、`jpeg-qualification.json`：复用 CTS 后的 route、共同测量、完整数据交付、SDK 与七项同值证据。
- `runtime/experiments/jpeg/a19-jpeg-environment/`：EF 工具能力 probe、镜像/源/库/SDC/专业绑定和环境冻结。

本片未修改 `flow_recipe.py` 或任何专业算法。没有证据支持的源码修复不实施；picorv32 与 UART 的拒绝保留。EF、DF 服务及九个子模块版本不变，用户已有修改不纳入构建或部署。

本片改动只有本报告及根 `PROJECT.md`、`ARCHITECTURE.md`、`TASKS.md`、`README.md`、`admin/STATUS.md` 的当前状态说明；A20/A21 的代码、测试、接口和逐文件职责见各自报告及本轮计划。Ruff/Pyright、根 304 测试的既有通过回执保留，文档差异检查和 26 份用户文件保护在总收尾再次核对；运行数据、恢复脚本和审计账本均留在 `var`，不混入源码提交。

总收尾 `jpeg-final-acceptance.json` 再次核对来源/复制 SDK、冻结环境及其正式入口检查；环境 ID 为 `de13559afeb1faa68af1628a2aa74f5ea77b47cc07ab22cfd60c8649692ba973`。`runtime-audit.json` 从本轮已保存公共 EF 回执查回 **142 个 run：139 succeeded、3 lost、0 在运行**；公开 health 的 worker 空闲、队列和资源预约为零。此账本限当前已知根业务/native/验证引用，不包括无关业务、全部历史或模型总成本。

已报告 CPU 合计 **22,879.37 秒**，三个失联 attempt 的 CPU/峰值未知，保留为未知而非零；它不是全工作流精确总成本或同预算比较。`protected-files-verification.json` 确认 **26 文件 hash 不变**，`SOURCE_MANIFEST.json` 与基线完全相同；根文档差异检查通过。业务代码后续没有再改动，不为文档收尾重复昂贵测试。

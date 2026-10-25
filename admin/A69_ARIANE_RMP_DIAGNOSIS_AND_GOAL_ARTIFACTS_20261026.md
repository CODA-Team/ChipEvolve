# A69：Ariane 原生重构诊断与 Goal 准备产物补齐

本切片完成工程检查，待老板业务验收。解决一处真实的产物登记缺口，并将 Ariane 的问题进一步定位到重映射候选质量；本轮没有新增可采用 PPA，也没有恢复正式长搜索。

## 业务交付

1. Goal 准备阶段生成的 `node.csv`、`nets.csv` 现在随设计输入一起由 EF 登记，可从公开产物接口完整取回。Agent 不再依赖仅存在于原工作目录的两份文件。
2. Ariane 原生 RMP 已实际进入候选和时序试评。四个逻辑区域、16 次试评全部变差并拒绝；查明了单元数量、局部线长和时序同时恶化的具体表现。
3. 拒绝后全部 210,746 个实例与 191,607 条网络的型号、位置、方向、放置状态、引脚连接、网络类型和供电连接恢复一致。没有把失败候选留给下一棒。
4. 三个中间节点均经 EF → DF → DI → 安装版 Query 读取，setup/hold 共六次精确查询及来源原件字节/SHA 核对通过。

## 具体代码修复

`chip_evolve/native.py::run_goal` 原来在 EDA 运行前用 `bench.glob("*")` 生成捕获清单。CSV 是该命令运行时才生成的，因而实际文件和原专业输入 profile 存在，EF 归档却遗漏它们。

改为显式声明准备脚本、四份设计文件和两个 CSV，共七份产物。没有改变函数签名、公共契约、EDA 命令、原专业算法或采用规则；适用于所有使用此入口的设计，不是 GCD 特判。

真实短验证使用已有 GCD G02 的已物化结果，经过正式 `run_goal` 准备入口和 EF 后，在进入原生控制器前显式停止：

| 产物 | 字节 | 含表头行数 | 公开 EF 取回与 profile 哈希 |
|---|---:|---:|---|
| node.csv | 19,356 | 440 | 一致 |
| nets.csv | 16,166 | 382 | 一致 |

生产 run 为 `run-bd1eecc1973e4de2aeba8613e2c491e5`。源设计保持原 SHA；没有启动新 baseline、构建、模型或演化。该验证不代表完整 Goal 搜索。

## Ariane 单阶段诊断条件

- EF run：`run-42f1ae9bd99f4370869a2836cc43e6f3`，正常结束；原生工具约 657.84 秒。
- 使用 A68 已构建并核验的二进制，SHA `ebb639395d646ade26b0067c1f88bcaacd09f9668e865880030604dee2c8ff79`。没有重新构建或改变 C++。
- 冻结 A62 的原生 DEF/V/SDC、原库与 RC 表，FF、900 ps、I/O 180 ps；保留原 `rmp_delay_timing / timing_only` 配方，最多四个逻辑区域、一次接受。
- 原生成器输出在 `post_rmp_restructure` 后停止，只增加原生功耗缓存刷新、标量/关键路径观察。没有额外 `repair_power`、`repair_timing`、GRT/DRT 或模型调用。
- 这是 **placement estimate**，不能与 A64 的 GRT 或最终 RCX 数值直接相减当收益。

## 同条件节点事实

| 节点 | 功耗 mW | cell 面积 µm² | setup WS ns | setup TNS ns | hold WS ns | hold TNS ns | slew/cap/fanout |
|---|---:|---:|---:|---:|---:|---:|---|
| 原生读入 | 642.205298 | 43653.386683 | −0.436833 | −231.138507 | −0.132263 | −144.216987 | 15/0/0 |
| 原生 repair_design 后 | 642.252982 | 43656.594784 | −0.436833 | −230.784699 | −0.132263 | −144.399909 | 0/0/0 |
| RMP 全部拒绝后 | 642.252862 | 43656.594784 | −0.436833 | −230.784699 | −0.132263 | −144.399909 | 0/0/0 |

`repair_design` 清除 15 个 slew，setup TNS 略改善，但 hold TNS 略差。RMP 未接受，前后时序/面积同值；功耗约 0.000119 mW 的浮点变化不计收益。序列化网表/ODB 字节不同，另用无序语义状态核对了完整回滚，不能宣称原始文件同字节。

## 为何候选失败

原生检查 512 条路径，选择 `axi_req_o[143]`、`[158]`、`[113]`、`[145]` 四个输出端点，逻辑区域含 36、36、34、35 个单元。每个区域按原策略运行四种映射，总计 16 次 STA。

- 试评单元增至 79–106 个，局部面积随之增加。
- 局部 HPWL 是原来的 21.63–27.81 倍。
- setup WS 从约 −0.437 ns 恶化至约 −5.26～−7.15 ns；全部同时触发 TNS/WNS 拒绝条件。
- 每次触发器引脚连接差异为零；最终整个设计回滚语义一致。
- 日志显示替换单元的局部漏电显著下降，但尚未保留映射文件逐项确认单元分布。因此“选到了低漏电慢单元”只是待核假设，不能写成已证根因。

原有源码提供 `RMP_NORMALIZE_BLIF_TO_SLVT`、`RMP_PLACE_BY_BOUNDARY_NETS`、`RMP_KEEP_ABC_FILES` 等开关。下一切片先核对其确切作用，再做一次有理由的短策略对照，并保留映射文件，不重复默认搜索、不删除原 STA/回滚保护。原默认放置是轮流使用原单元位置，并非所有单元放到原点。

## 验证与 code-check

- 从 Git 原始 `run_goal` 编译出的隔离版本：两项测试均准确复现缺 CSV；修复版两项通过，覆盖 `gcd` 与 `ariane_tile`。最早一份 before 日志发生并行读取竞争而通过，不作为修复前证据；采用 `immutable-before-artifact-regression.log`。
- 全部已跟踪根测试 **733 passed**；新增测试只计一次。Goal 源码和生成器保持同 SHA，复用 A68 的 **475 tests / 52 subtests**，未重复整场测试。
- 产品和本轮校验脚本的 lint、format、类型检查、逐文件差异和模块边界检查通过。code-check 指“本轮实际检查结果”，不是外部独立审查认证。
- 保留 26 份用户在途文件哈希、DF/DI 修改和历史来源；唯一根业务 Python 改动是 `chip_evolve/native.py`。
- 诊断 r2 因额外 fanout 计数在其原生初始化前调用而崩溃；r3 先运行原 `report_check_types -max_fanout -violators` 后通过。已有产品物理测量入口顺序正确，没有为此修改 OpenSTA。私有发布脚本初次沿用另一种 cloud 日志格式，提交事实前断言失败；修正解析后复用同一 EDA run，不重跑设计。

## 文件职责与数据流

| 文件 | 本轮职责 |
|---|---|
| chip_evolve/native.py | 显式登记 Goal 准备输入与生成检查文件 |
| admin/test_goal_preparation_artifacts.py | 验证运行前声明尚未生成的文件，覆盖不同 top 名称 |
| 本报告 | 业务结论、诊断条件、失败原因和验证限制 |
| admin/A54_CURRENT_BLOCKER_MAP_20261025.md | 更新当前阻断和下一具体动作 |
| admin/STATUS.md、TASKS.md、ARCHITECTURE.md | 当前恢复点、切片状态和现有边界说明 |

数据流：已有物化设计 → Goal 准备 → EF 执行/七产物登记 → 原专业 profile；另一路 Ariane 原生阶段 → EF 归档 → 原 ORFS adapter → DF → 安装 DI/Query → Codex 决策。行为调整仍在原 `run_goal` 与原专业策略中，不增加包装层。

本轮证据目录：`var/business/a69-ariane-native-rmp-20261026/`，以 `code-check.json`、`fact-verification.json`、`rollback-verification.json`、`preparation-artifact-verification.json` 为入口。八组两次完整合格结果、Ariane setup 闭合和剩余最终物理/功能资格仍未完成。

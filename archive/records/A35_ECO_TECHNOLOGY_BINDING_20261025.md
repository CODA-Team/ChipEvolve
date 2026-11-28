# A35：ECO 的物理库与推理参考一致性修复

本切片接续 A34。长优化搜索仍暂停，只修真实接入阻断，原 ECO 动作、模型提示主体、评分、回退/最佳状态规则与布线校准策略保持。

## 问题与实际修复

原 OpenROAD 入口已接收显式 `TIMINGECO_LIB_FILES`，但生成专业推理参考时没有传该清单：提取器仍按 ASAP7 分组/VT/corner 搜库，且将 ps/fF 当隐含单位。加载器还在已读入其他技术 ODB 后继续加载写死的 ASAP7 LEF。这会使工具看到的设计与模型用于判断的技术信息不一致。

本轮修改：

| 文件 | 职责与变化 |
|---|---|
| `chip_evolve/native.py` | 把现有冻结 Liberty 清单同时传给参考生成任务；corner 使用实际设计声明，未声明仍保留 FF 默认。共享接点只影响 ECO 准备，不改 Flow/DPL/Goal。 |
| `timing-eco-agent/src/extract_liberty_tables.py` | 显式库优先，逐文件将时间/电容换算为 ps/fF；支持 Nangate45 `_X` 名称与常见空白写法。保留原单元族选择、最差 arc、插值/约简机制。显式缺库或没有可用单元时报告失败。原文件同步格式检查。 |
| `timing-eco-agent/OpenROAD_utils/OpenROAD_load_design.tcl` | 显式平台模式使用 ODB 自带技术/masters，不叠加旧 ASAP7 LEF；独立原生模式保留原默认加载。 |
| `timing-eco-agent/src/test_liberty_reference.py` | 覆盖明确选库、不同命名、ns/ps、pF/fF、gzip、缺失库与空输出。 |
| `timing-eco-agent/src/test_library_binding.py` | 覆盖平台不额外读旧 LEF、独立模式仍读原五份 LEF/十五份库。 |
| `admin/test_eco_pdk_binding.py` | 验证 session 与参考生成收到同一清单和实际 corner，保留原资源/DRT 策略。 |
| `timing-eco-agent/PLATFORM.md` | 记录实际技术绑定与本轮验证边界。 |

沿用原环境字段、CLI、EF/DF/DI 与既有 SDK；没有新服务、API、数据库或 harness。源于第三方的署名与 NOTICE 保持。

## 逐步证据

修复前四个针对性测试均失败，原日志保留。修复后 ECO **25** 项回归、根接入针对性 **35** 项、完整根业务 **654** 项通过；Ruff 未定义/未使用检查、修改文件格式检查、Pyright、两仓库 `git diff --check` 通过，26 个用户保护文件哈希保持。

原 ASAP7 FF 默认参考与新提取器对照：**309 个单元全部输入电容/延迟/转换时间网格逐值相同**。不是仅比较单元数量；没有弱化专业分析能力。

通过 EF 实际生成参考并加载原 ODB/SDC/SPEF，不运行优化或模型：

| 输入 | EF run | 参考结果 | 重新加载 setup WS/TNS（ns） | 判断 |
|---|---|---|---|---|
| GCD/ASAP7 历史 baseline | `run-3b6034bbf0aa4c27b6ae76c5f8025584` | 309 cells / 38 families | +0.00934292 / 0 | 与原汇总精度一致 |
| JPEG/Nangate45 历史 baseline | `run-8c79fe8342fa4b8ba5d257869e61dd0d` | 78 cells / 26 families，无 ASAP7 内容 | −0.108898 / −37.5624 | 与原汇总精度一致，原输入时序仍不合格 |

原生 `worst_slack` / `total_negative_slack` 的未舍入值与原 JSON 六位有效数字不能直接用固定绝对阈值比较；最终按原序列化精度复核，未重跑 EDA、改动原指标或放松业务约束。最终收据保留未舍入值与原值两列。

诊断过程也保留自身错误：r1 探针漏传容器 cleanenv 所需的环境变量；r2 查出 JPEG 旧配置 PDK 路径不存在。前者只修新探针，后者只在新私有配置显式选择实际 `goal-pdks/jpeg`，不修改历史实验。这两项不冒充专业算法失败。最终运行的提取器逻辑 AST、加载 Tcl 与最终源码分别核验一致。

## 接续方式与未完成项

八份接续配置在 `var/business/a35-eco-technology-binding-20261025/configs/`，相对 A34 仅新状态目录与正确 ECO PDK 模板；JPEG/Nangate45 的不存在 Goal 模板也在新配置中纠正。使用该目录的明确配置，新任务冻结当前模块提交，历史运行副本保持。

数据流：原 result/DF scope → 现有接入层冻结相同库/PDK → EF 生成专业延迟参考及执行 OpenROAD → 原 ECO 控制器消费相同技术信息。修改选库/单位行为在提取器；修改接入传递在 `native.run_eco`；修改物理加载在原 Tcl。

本轮仅证明环境/参考输入正确，不表示 Nangate45 ECO 完整策略已经取得 PPA 收益，也不表示八组双次已完成。A34 的手工 GRT 修复已通过两动作验证，但完整收尾 PPA 尚未运行。Ibex/Nangate45 原证明共 19384 分区，本轮只读看到 5333 个 strategy PASS，原 1800 秒超时仍属未完成；不是缺少 PASS 文件的收尾误判，也未发现可据以宣布完整证明的证据。下一步继续具体功能阻断/短验证，不能借本轮修复直接放行所有长任务。

证据目录：`var/business/a35-eco-technology-binding-20261025/`，重点是 `technology-probes-final.json`、`asap7-original-reference-equality.json`、`final-source-and-protection.json` 和前后/回归/静态日志。运行数据不提交 Git。

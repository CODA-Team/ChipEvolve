# A62：Goal 原生输入、时钟与寄生模型边界诊断

基线根 `f612667`，Goal `d41efa2`。接续 A61，对 Ariane/ASAP7 的实际时序欠账做定点核查。本轮没有产品源码、服务、容量、公共接口或历史实验修改；没有 Teacher/Student 演化或模型调用。短验证使用公开 EF 和已验证的 A38 二进制，专业策略保持原定义。

## 先排除错误修复方向

源码中有 `set_ideal_network [all_clocks]`，但不能只看到这一行就断定专业评价偷偷采用理想时钟。在同一份原始 ODB、SDC、SPEF、21 库及二进制下，分别测试时钟指令和寄生模型：

| 测试指令 | 寄生模型 | setup WS / ns | setup TNS / ns | hold WS / ns | hold TNS / ns |
|---|---|---:|---:|---:|---:|
| `set_propagated_clock` | 原 SPEF | −0.288838128257 | −127.167513896 | +0.009735351689 | 0 |
| `set_ideal_network` | 原 SPEF | −0.288838128257 | −127.167513896 | +0.009735351689 | 0 |
| `set_propagated_clock` | placement 估算 | −0.436087345245 | −229.142109106 | −0.131862302587 | −143.297019195 |
| `set_ideal_network` | placement 估算 | −0.436087345245 | −229.142109106 | −0.131862302587 | −143.297019195 |

四份原生报告实际均写明 `clock network delay (propagated)`。这里的第二种指令没有清除该 SDC 的传播时钟行为；不能将场景文件名中的 ideal 当成实际时钟状态。此控制否定了本设计上的时钟猜测，因此不实施猜测性的 clock-mode 补丁。

RC 模型确实显著改变数字，且本次 placement 更差，并非单向制造乐观结果。该差异是测量边界，不是 Agent 产生的物理收益。EF `run-0454aa5316114ecd86a291313dbc78ed` 成功，约 136 秒，四个场景均原生退出 0。

## 按真实专业入口诊断

`chip_evolve/native.py::run_goal` 的入口先复制父产物，再通过 EF 去 filler、规范 DEF 单位、移除信号 dbWire、保存 DEF/网表/ODB及原生 node/net CSV。Goal 正常评价从准备后的 DEF 与网表重新加载；原评价源码明确禁止把父级 post-route ODB 当成第二次优化捷径。本轮完整复用这一入口含义，不向 `_write_tcl` 传 `parent_checkpoint`。

父 SDC 相对目标源文件仅增加日期注释及 `set_propagated_clock [get_clocks {core_clock}]`。其余有效约束命令逐行一致，原时钟 900 ps、I/O 180 ps 保持。目标源 SDC、目标条件与库先按现有函数核对；父级实际 SDC 原样用于本次专业接力，额外命令与 SHA 单独记录。

私有 Goal PDK 保留原 setRC 并显式追加既有 signal/clock layers；其 21 库 SHA 集合与冻结设计一致。实际 Python 生成器来自当前 Goal 项目，官方工具 Tcl 与原绑定逐字节相同。执行使用 A38 已修复二进制 `e4ba970b3edd091d90b32fd691e353c59a92414955e8aa5b902e4a0f5e0500d0`，没有重建。

原生 `crit_vt_deep` 命令保持：

```tcl
repair_timing -setup -phases {CRIT_VT_SWAP TNS LAST_GASP} \
  -sequence {vt_swap sizeup swap sizeup_match buffer} \
  -repair_tns 30 -max_repairs_per_pass 2 -max_passes 2 -max_iterations 2
```

目标 TNS 绝对值为 0，模式为 timing_only。保留 repair_design、原生时序策略、Diamond、improve_placement、mirroring、placement RC 刷新、GRT与 GRT RC 刷新及官方 node/net 导出。工具线程与 EF 申请均为 4，16 GiB、2048 进程，900 秒确定性诊断预算；服务总容量保持。

## 本轮阶段结果

原生准备 `run-13cc0d5a5bde4a839071215d44bdd243`、完整专业执行 `run-d2429561bfb443b0ae4925b9c3af91fa` 均成功。工具原生退出 0，墙钟约 851.23 秒，EF 整体约 872.37 秒、CPU 2058 秒、峰值约 3.58 GiB / 5 进程；没有触发资源或超时终止。

| 原生检查点 | RC 模型 | setup WS / ns | setup TNS / ns | 总功耗 / mW |
|---|---|---:|---:|---:|
| pre_repair | placement | −0.436833415138 | −231.138506877 | 642.205298 |
| post_repair_design | placement | −0.436833415138 | −230.784699217 | 642.252982 |
| post_repair_timing | placement | −0.428783076737 | −203.239315574 | 642.804384 |
| post_placement | 刷新的 placement | −0.423485314358 | −191.151590633 | 642.146170 |
| post_route | 刷新的 GRT | −0.433790404764 | −451.843204974 | 648.287177 |

repair_design 在 9 条网上插入 12 个 buffer；critical-VT 首个阶段表记录 737 次调整，完整时序修复最终记录 **3388 次 VT 调整**、违规端点 4625→4449，原生提示无法修复全部 setup。placement 口径下，从初始到合法化后的 TNS 欠账减少约 17.30%，但没有闭合。Diamond、improve_placement、mirroring 和最终 check_placement 实际完成，未报告重叠、行/站点对齐或边距错误。GRT 末尾报告 164 条 slew 违反；其 RC 模型与原 SPEF 不同，不能直接拿该计数与原 444 条作同口径改善率。

## 同口径控制避免误诊

从 post_placement 到 post_route 的变化看起来像“收益被吞掉”，但这两行采用不同寄生模型。额外只读核对 `run-861523c15eed4411aad55b053df8a884` 证实，两份 ODB 的 **210746 个实例的 master、位置、朝向、放置状态签名完全一致**；三份 post_repair_timing / post_placement / post_route 网表逐字节相同。GRT 新增 1604090 条 guide，详细布线信号 dbWire 均为 0。因此不是下一专业偷偷换回网表，也不是最终 DRT。

再将**未优化 pre_repair 起点**按相同二进制、SDC、库、setRC、层范围、GRT 参数及功耗刷新协议测量，只做 GRT/读数、不做单元优化。控制 `run-693be0f9f8c64e41bf55b84828e48625` 成功，输出网表与 pre_repair 逐字节相同：

| 同一原生 GRT 协议 | setup WS / ns | setup TNS / ns | 总功耗 / mW |
|---|---:|---:|---:|
| 未优化起点 | −0.441743709670 | −509.059148799 | 648.190737 |
| 完整 crit_vt_deep 后 | −0.433790404764 | −451.843204974 | 648.287177 |

在这一可比口径下，TNS 欠账减少 **11.24%**，最差 slack 改善约 **7.95 ps**，总功耗略增约 0.09644 mW。专业修复实际有效，幅度仍不足以闭合；不能宣称收益全部丢失，也不能将它写成最终提取 RC 下的 PPA 改善或采用结果。该控制是同一研究起点的测量对照，不是第二次独立协同优化。

初始 placement 功耗报告明确采用 Watts：总量 642.205298 mW，其中 Macro 429.138422 mW、占 66.822624%。这说明优化对象构成与小型 GCD 不同；并不证明所有后续状态宏功耗恒定，也不能据此算出可保证的优化上限。核查 OpenSTA 源码及原生标题后，现有阶段 pW 换算正确，无需单位补丁。

## 验证与 code-check

证据目录为 `var/business/a62-goal-clock-boundary-20261025/`。

- 五个原生阶段分别经既有 ORFS metadata adapter→EF→DF→DI/Query 登记与逐值核验；Query 精确范围均回答成功，原 metadata 字节与来源 SHA 一致。功耗原始报告为 W、表格换为 mW；时序保留 ns。阶段绝对值解析另与原日志中的带符号值交叉核对。
- 同协议原始起点控制另外登记快照 `a62-run-693be0f9f8c64e41bf55b84828e48625-matched-grt-control`。Query 的实际 `--compare-runs` / global_route 比较同时返回 −509.059148799 与 −451.843204974ns，完整回执在 `matched-control-facts-receipt.json`；不是手填比较结论。
- 27 项相关根测试通过，覆盖原生阶段事实、专业 handoff、Goal 路由控制和双 PDK 绑定；七份私有 host 驱动 lint、格式和 Pyright 通过，类型检查 0 errors / 0 warnings。产品代码与 A61 相同，复用 A61 的 712 根业务回归及 42 ECO / 2 子测试，不冒充本轮重跑。
- 所有冻结原输入、目标、库、源 result、实际生成器源码与二进制 SHA 保持；26 个用户保护文件及原有 generic_agent / DF / DI WIP 保持。原失败来源与 adopted=false 不改，收口时 EF 五种活动状态均零。

私有驱动初次严格套用最终 SDC 字节断言、重复创建目录和实际解释器来源断言均有失败日志。已按真实入口及实际同内容工具来源纠正，仅完成一次 EDA 输入准备，没有为这些脚本错误重跑同一个物理阶段。直接脚本调用会优先消费 Goal 环境已安装的旧控制器；本轮改为在 Goal 自有目录用其解释器执行 runpy，实际源码路径和 SHA 单独验证，不注入跨项目 PYTHONPATH。这是私有验证入口纠正，不是宣称原 `-m goalevolve.cli` 产品入口有同样错误。

物理签名附加核查最初错误选择了共同镜像未启用的 OpenROAD Python 入口，`run-a03b3446b58b43ae8d436174b6dc09be` 失败原件保留。改用已有 Tcl/OpenDB 接口只读导出并比较，未安装 Python 绑定、替换镜像或重做专业修复。成功 Tcl 核查由 EF 管理，原实例逐项签名及新增 guides 均有登记原件。

## 当前业务判断

当前证据不要求新增服务或重构架构；本轮也没有足够理由改专业算法或时钟处理。需要区分三个判断：专业动作是否实际发生；同一估算阶段是否改善；最终布线提取与功能资格是否通过。本轮前两项得到真实证据，第三项仍未通过。

下一项应核查这套专业 GRT 估算与共同最终 RC 口径的关系，再依据实际时序债与已有专业策略决定后继。不能仅因“流程成功”放行正式搜索，也不能仅因跨 RC 模型的数字差额就添加时钟/交接补丁。此分支不做最终 DRT/RCX、功能证明或采用，不计作两次完整协同优化。

本轮发布文件仅本报告、A54 当前阻断表、TASKS、ARCHITECTURE 和 STATUS。私有驱动、CSV、原生 ODB/网表、日志、对照及检查回执留在 var，不发布为产品接口或框架。

不放宽原条件，不把原失败父项或诊断检查点改成合格结果。Ariane 两 PDK 最终资格、Ibex/Nangate45 完整证明、GCD/Nangate45 500 ps 新协作及八组双次仍是后续任务，长搜索继续暂停，总目标保持进行。

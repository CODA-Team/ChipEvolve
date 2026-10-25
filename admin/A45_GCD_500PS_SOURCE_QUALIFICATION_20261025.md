# A45：已批准500ps条件的完整GCD来源资格

本轮接续根 `e87544e`。A32–A44已完成相关具体阻断修复与短验证，本切片只运行一次已批准 GCD/Nangate45 500ps 新条件的完整物理来源资格，不启动 Flow/Code/ECO 搜索或模型，不修改运行中的产品代码。不是八组双次正式实验已完成。

## 业务结果

通过原业务CLI、原 EF/Toolkits 和固定共同镜像，从GCD RTL完整执行综合、布局、CTS、详细布线、RC提取、共同测量及三类事实入库：

| 指标 | 新500ps来源 |
|---|---:|
| 功耗 | 2.2321124561 mW |
| cell/core/die面积 | 675.64 / 1076.77 / 1278.42 µm² |
| setup最差裕量 / TNS | +40.0912 ps / 0 ns |
| hold最差裕量 / TNS | +110.517 ps / 0 ns |
| slew / cap / fanout违反 | 0 / 0 / 0 |
| placement违反 / 原生DRT | 0 / 0 |

原物理阶段使用NS、综合ABC使用500ps；9份已展开阶段SDC均有物理/虚拟时钟0.5ns，综合输入SDC保留原变量模板且与批准文件字节完全一致。共同测量实际报告两时钟0.50ns；最后显式PS文件为500ps，I/O延迟100ps，20%公式含义保持。

这是**新条件基线**，不能把它与旧250ps结果的差别说成协同优化收益。新 condition_id 为 `c001ce1866989fd53f7f39103f05ce814a0af0d601451719d10558b1592820dd`；旧250ps实验与负结果不改写。只运行一次，不计算两次均值，不声称已采用候选或完成额外功能证明。

## 原执行与事实链

| 任务 | 公开 EF run | 结果 |
|---|---|---|
| 完整ORFS | `run-c6f10855fb764a378f58d578f2c524d0` | succeeded |
| 共同测量 | `run-9b90f0c354b948a9b92dec51aec3a7cd` | succeeded |
| OpenDB导出 | `run-d94a857c14254f77bc1650be506f4825` | succeeded/DF已导入 |
| OpenSTA导出 | `run-8afac8e1d3f149589911e770c67acfa8` | succeeded/DF已导入 |
| ORFS指标导出 | `run-b8a1f895386241d89a608174a1cc8f73` | succeeded/DF已导入 |

已独立核对全部成功状态、父子标签、原ODB/SDC/SPEF/V/DEF登记SHA、三snapshot作用域及导出producer。DF/DI的12个原始PPA/违反数值与结果逐项相等，已安装A33 Query精确run/snapshot/revision查询WNS、TNS均 ANSWERED。WNS按定义截零，setup正裕量仍独立记录为+40.0912ps，不能混淆两者。

`STA-0450`仅说明虚拟时钟不能传播，原日志保留；物理时钟传播和虚拟I/O时钟约束均按原工具执行，不静默消警告。

## 环境、代码检查及边界

启动前实核镜像完整SHA、全部Liberty SHA、批准500ps SDC、实际32CPU/32GiB容量、空队列与DF健康；资源仍为现有GCD8线程/4GiB，未改容量。运行前记录业务入口/包内Python文件SHA，结束后逐项相同；26个用户保护文件保持。原物理与事实模块没有修改，复用A44的689根回归及既有模块门禁，不为数据验收再写模拟产品测试。

检查脚本最初误以为所有阶段SDC都已展开、原文件在实验根目录、scope摘要包含producer；读原件/现有API后分别改为验证原变量模板SHA、`native/`目录和显式`detail=full`，失败日志保留。没有为这些检查错误重跑任何EDA、导入或修改历史原件。

证据：`var/business/a45-gcd-500ps-source-qualification-20261025/` 的 `preflight.json`、`source-qualification.json`、`qualified-source.csv`、各Query输出及原实验目录。单次资格数据不会覆盖既有论文表或自动当作正式双次结果。

## 下一项实际阻断

完整新来源已物理闭合，但原生Flow接入的两处文本假设拒绝这份原工具已成功加载的SDC：`prepare_native_source`要求单位声明是文件首行，不接受前导注释；`flow_sdc`只接受数字字面量时钟，拒绝原生`clk_period`变量及匹配虚拟时钟。已用本来源原件直接复现，0新增EDA/模型，证据在A46的 `actual-blockers-before.json`。

下一切片只恢复已授权的原生变量时钟接入、接受明确单位前的注释，不改时钟/IO数值、不解释任意Tcl、不缩减Flow参数域。它修好并短验证之前，不启动完整专业搜索。Goal新任务也应根据当前“时序已闭合”的事实选择原生功耗/面积策略，不能机械沿用旧250ps时序修复任务。

# A52：Ariane 最终供电检查与失败分支收口

2026-10-25 A55更正范围：本报告验证的是旧 `run-d054…` 来源及其事后改网格，负结果保持。另一个布线前应用修正PDN的 `run-9efb…` 实际已完成原ORFS最终VDD/VSS PSM，之后因缺少SRAM GDS失败；此前没有把该分支纳入清单。不得把下文“只有floorplan通过”的判断推广到全部修正来源，详见 [A55原件核查](A55_ARIANE_CORRECTED_PDN_SOURCE_RECOVERY_20261025.md)。

接续根 `dd290db`。本切片未改产品源码，只验证仍未闭合的实际供电阻断；不启动长搜索或重新布线。

## 实际检查

复用原失败完整ORFS `run-d05441469fa744d2856ec6c24de5aa12` 登记的最终ODB，实际SHA与EF原件相同。诊断先检查原ODB，再用已通过floorplanning的既有PDN配置重建供电网，在当前最终布局上运行**完整实例**check_power_grid，无-floorplanning。

配置与原PDN文本核对，唯一参数差别仍是M5 offset0.300→1.380µm；未调条带宽度/间距/周期、宏布局或业务约束。新原生EF `run-903b7a35c9dc4ea9a0a2827e9705c0f6` 执行122.69秒，正常退出，实际结果为：

| 状态 | VDD | VSS |
|---|---|---|
| 原最终ODB完整实例检查 | 失败PSM-0069 | 通过 |
| 旧信号布线保留、重建PDN后 | 失败PSM-0069 | 失败PSM-0069 |

后者出现大量供电线与既有信号线的短接告警，VSS达到10000 shorted-shapes报告上限。**EF任务执行成功不等于供电检查通过**，final-connectivity-check明确power_grid_passed=false；未采用，也不是完整合格基线或一次成功重复。

## 这项证据改变了什么

本轮纳入的A30证据只有floorplan/fixed-instance检查通过；不能将这份前置检查升级为完整最终供电资格。A55随后从另一个已完成修正来源找回了原生最终PSM通过证据，见页首更正。事后把新网格加到旧详细布线之上不是有效修复路线；前置修正与事后重建是不同分支。本轮停止事后改网格尝试，不继续搜索其他偏移或放宽检查。

本次不是原ORFS final_report的逐命令等价重放，只是对登记最终ODB的完整原生check_power_grid诊断；原ORFS自身失败结论仍独立保留。不能据此把新相位配置本身判成整体流程一定无效，也不能把floorplan通过当最终通过。

前后DEF的COMPONENTS/NETS/PINS段一致，说明既有实例放置及信号布线未重做；Verilog字节不一致，新pdngen增加显式VDD/VSS顶层端口，因此不声称网表同值或完成功能证明。原最终ODB、PDN原件与26保护文件SHA保持。

## 统一事实与门禁

原生TSV/DEF的EF登记manifest与实际SHA核对通过。四项0/1连通结果经既有EF→ORFS事实适配器→DF→DI回流，快照 `a52-run-903b7a35c9dc4ea9a0a2827e9705c0f6-power-grid`，原值逐项一致，power_grid_passed/adopted明确false；未补造PPA。

运行证据在 `var/business/a52-ariane-final-power-grid-20261025/`：preflight、native-tool-result、final-connectivity-check、fact-publication-check、DF-diagnostic-facts和原脚本/日志。产品与研究源码未改；复用当前A51的192Query/712根回归及已通过静态检查，不为数据观察再写模拟产品测试。原服务/资源容量保持。

本报告、TASKS、STATUS是本轮唯一提交文件。本轮旧来源和事后重建负诊断不作为正式就绪；另一前置修正来源的实际最终PSM与剩余PPA/GDS问题后来由A55核实，后续以该具体分支证据推进，长搜索仍暂停。

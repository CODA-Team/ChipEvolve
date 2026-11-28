# A60：修复 ASAP7 FakeRAM benchmark 的抽象宏导出声明

基线根 `e86297b`。本轮找到了 Ariane/ASAP7 末端 GDS 错误的输入模型原因，并完成原生正反对照、实际 GDS 核验及 EF→DF/DI 事实回流。没有重跑布局布线、供电、PPA 或专业模型搜索；产品代码、公共接口、服务和原实验保持。

## 来源核查改变了什么判断

`goalevolve/third_party/benchmarks/asap7/README.md` 明确说明这是 OpenROAD 所需的最小文件集，SRAM 来自 **FakeRAM2.0**，提供 Liberty 与 LEF。当前 DEF 实际使用一种 `sram_asap7_16x256_1rw`，共 **136 个实例**。

原生 ORFS 已提供 `GDS_ALLOW_EMPTY` 来支持这类抽象宏，但当前默认 `fakeram.*` 与该 benchmark 的宏名称不匹配。因此原任务已完成 DRT/RCX/final_report/PSM 后，在流片格式导出时报告缺宏。

A55 记录的“缺少 SRAM GDS/OAS cell”仍是准确原生事实；进一步查明输入本来采用抽象 SRAM 后，当前研究 PPA 的接入处理应显式保留该模型，并声明抽象宏导出范围。真实 SRAM 内部几何仍未提供，本轮不生成它。原时序/电气约束与库模型保持。

## 修改与原生短验证

只在新私有配置中添加：

```make
# FakeRAM2.0 benchmark supplies LEF/Lib abstract memories; streamout remains abstract.
export GDS_ALLOW_EMPTY = ^(?:fakeram.*|sram_asap7_16x256_1rw)$$
```

末尾 `$$` 经 GNU Make 导出后为正则中的 `$`。实际 Make 环境读取已验证；额外 SRAM 类型、名称后缀和标准单元不匹配新增规则。

从公共 EF 原归档恢复精确 `6_final.def`、原 `klayout.lyt`、tech LEF 和已冻结七份 LEF，使用同一固定镜像、原生 KLayout 0.30.12、原 `def2stream.py` 和原三份标准单元 GDS。只变 `GDS_ALLOW_EMPTY`，两次原生命令结果为：

| 同输入控制 | 原生退出码 | 实际观察 | 工具墙钟 |
|---|---:|---|---:|
| 原默认 `fakeram.*` | 1 | 复现同一个 SRAM 缺 GDS/OAS 错误 | 19.99秒 |
| 显式 benchmark 抽象宏声明 | 0 | 仅该 SRAM 被报告为已声明的抽象宏，导出成功 | 16.57秒 |

之后用实际 KLayout 读取新 GDS：顶层 `ariane` 非空、共249个 cell，唯一空 cell 为上述 FakeRAM，136个实例全部保留。完整 SRAM 晶体管级几何仍为 false。控制试验和失败记录不计入两次独立 PPA 优化或均值。

EF `run-e95000de675449199a65f792c32807df` 成功，整体约55.76秒、CPU49.59秒、峰值约1.49GiB、6进程。新导出为278,550,844字节；大小相同不作为内容相同的证明，实际文件和来源另核 SHA。

## 下一轮实际消费的配置

新配置 `var/business/a60-asap7-fakeram-streamout-20261025/future-ariane-asap7.json`，只改变原A54配置的私有 state_root 与显式 baseline_overrides。其原生生成方式“原模板 + overrides”与本次验证过的 design.mk **逐字节一致**。

已确认保留原 `PDN_TCL=/work/inputs/compatible-pdn.tcl` 及对应依赖文件。21库、SDC、原目标、各专业配置、工具链及源码绑定保持；不会因为修末端导出而丢掉已验证的前置供电修复。未切旧配置、旧会话或已结束任务。

## 事实回流与已有 PPA

新事实导出 `run-bec637f98bd5436383100b08f73bd100`，快照 `a60-run-e95000de675449199a65f792c32807df-abstract-streamout`。六项维度为计数/标志的原始事实经 DF/DI 逐值核对：

- 抽象宏 streamout 完成=1；完整宏几何=0；完整 GDS 几何交付=0。
- 抽象宏类型=1、实例=136；原整场任务成功=0。

元数据保留 benchmark README、宏声明、原生对照、GDS SHA 和原失败父任务。沿公开 source excerpt 取回的 metadata 字节与输入完全一致。

新快照只有导出事实，按精确范围询问 WNS 时 Query 正确返回 `NEEDS_MORE_DATA`。原物理快照仍回答 **WNS −0.288838ns**，原 result SHA、原 failed 和 adopted=false 保持。没有把导出完成变成时序闭合或新增优化收益；原 setup TNS−127.168ns、slew444仍需修复。

## code-check、失败与文件范围

首次私有独立重放漏了原 Make 负责设置的 `KLAYOUT_CMD`，任务 `run-45f56dab3587425fbf32aab3cb5232e1` 在实际导出前失败；已在原生控制脚本中显式取得镜像内 KLayout 路径并恢复该变量。只在新的 r2 工作目录验证，旧失败、副本和日志保持，没有修改 ORFS 或服务。

私有核验首次试图从不含该字段的 evidence 行寻找来源，已删除这段无用读取，使用实际 EF export 的 raw metadata artifact 和既有公开 source 路由；仅重做读取核验，没有重跑两次导出。

五份私有脚本通过 Ruff、格式与 Pyright，14份公共原生文件逐件核 SHA；26个用户保护文件及 DF/DI WIP保持，EF活动队列为零。产品源码与A57检查点相同，复用根712项、ECO37项/2子测试及静态回归；本轮以实际原生控制、布局读取和公开数据核查验证变更。

提交范围为本报告、A54当前表、A55来源补充、ARCHITECTURE边界及TASKS/STATUS；运行脚本、配置、归档和版图仍在var。证据目录 `var/business/a60-asap7-fakeram-streamout-20261025/`，关键记录为 `preflight.json`、`short-check.json`、`facts-receipt.json`、`final-functional-verification.json` 和门禁日志。

当前研究导出配置阻断已修；完整制造版图不属于这份抽象 benchmark 的现有交付。下一项继续核查真实 setup/slew 债及专业动作，不再为已经完成的供电或这一名称不匹配重跑整场。八组双次、最终物理/功能资格和总目标仍未完成，长搜索继续暂停。

# A68：修复供电连线误筛候选，恢复 RMP 的实际试评能力

本切片工程验证通过，待老板业务验收。修复的是专业算法接收完整物理设计状态时的一个具体阻断，没有恢复正式长搜索，也没有新增可采用的 PPA 结果。

## 从业务上看，解决了什么

A67 已修复“选择了 RMP 重构策略却没有执行”的模式分支；本轮继续查“执行后为什么一个候选都没有”。真正原因是：原 `touchesSequentialPin` 把共用电源／地网络也算成触发器信号邻接。设计已经连接 VDD/VSS 时，大量普通组合单元因此被误筛掉。

这不是 Nangate45 整体不支持，也不是 Liberty 未绑定。两种读取入口和实际单元属性均已核对。修复后，原专业方法能够生成候选、实际运行 ABC/STA、按原规则拒绝差结果并回滚；没有用放宽验收来制造收益。

**设计及数据底座中的电源／地连接保持。** 只在该“信号依赖”判断中排除供电网络，不在平台全局删去电源事实。

## 根因证据

同一 GCD/Nangate45 250 ps 输入，经过 EF 只读核查：

| 核查项 | 实际结果 |
|---|---:|
| 实例数 | 737 |
| 原判断中的触发器邻居，含共用供电 | 735 |
| 排除供电后的真实信号邻居 | 167 |
| 其余条件下可继续检查的组合单元，诊断代理值 | 523 |
| DEF/V 与保存 ODB 的属性、连通判断 | 全部一致 |
| 实例 Liberty、Cell Liberty、映射 Master 与实际 Master | 737 项全部匹配 |

523 是只读准入代理数，不是接受的优化候选数；真正的候选与试评数量见下表。供电检查的 r1 准备脚本曾仍引用旧探针，该重复观察保留；最终比较使用增加实际引用断言的 r2，不能把 r1 算作独立供电对照。

## 修复范围及原算法边界

私有 OpenROAD 源码只改变 `src/rmp/src/Restructure.cpp` 的该判断：

```cpp
// Shared supplies are not sequential signal dependencies.
if (net == nullptr || net->getSigType().isSupply()) {
  continue;
}
```

其余信号邻接、单元可编辑性、时钟网络、顺序引脚保护、ABC、STA、面积/线长代价、候选数、接受数、快照回滚与晋升规则均保持。没有修改原时钟/I/O约束、库或目标。

原 A38 源码与二进制保持原字节，修复只用于新的私有副本。Goal 模块发布可复用补丁、说明和原生 C++ 回归，未改发布的研究 lineage。新源码重新构建并生成原生 AST 索引：160 个可编辑文件、1989 个符号。

## 实际原生验证

复用 A67 的完整原生 Tcl、冻结输入、四线程和原候选限额，除输出目录外命令逐字相同，只更换新二进制。任务由 EF 完成，原生工具墙钟约4.07秒；来源、源码与二进制均有独立哈希。

| 原生执行观察 | A67 修复前 | A68 修复后 |
|---|---:|---:|
| 分析路径 | 200 | 200 |
| 进入试评的候选逻辑云 | 0 | 4 |
| 真实 STA 试评 | 0 | 16 |
| 接受的逻辑云 | 0 | 0 |
| 试评中的触发器引脚连接差异 | 未进入试评 | 16 次均为0 |

16 次候选均被原 TNS/WNS 规则拒绝。日志保留具体前后时序与拒绝原因，不把“有候选”当作“有收益”。此输入仍是旧250 ps负状态：最后原生 GRT setup TNS −8.05189804289 ns、WS −182.555947748 ps、报告总功耗7.08364602178 mW。它不合格、未采用，不是批准的500 ps正式实验，也不是两次独立优化的均值。

原生任务：`run-f92e5f80f2c8431383a287b9d5795545`。

### 拒绝后有没有偷偷改变设计

补做一次 EF 只读检查，比较 RMP 前后：737 个实例的 Master、位置、方向、放置状态、全部引脚连接，以及761条网络的类型、特殊属性、内部连接和外部端口，排序后的内容/SHA全部相同，**包括供电连接**。

序列化 Verilog 字节不同，仅 wire 声明顺序变化，不能用文件 SHA 差异直接断言逻辑变化。这里没有修改原产物；以完整对象/连接比较确认回滚，而不是把变化覆盖回原件。

## 执行、数据与后续绑定

```mermaid
flowchart LR
  S[冻结的设计状态与供电连接] --> G[原生 Goal / RMP]
  G --> F[区分供电与信号邻接]
  F --> E[EF 实际候选与 STA 试评]
  E --> R[原规则接受或拒绝 / 回滚]
  R --> D[DF 阶段事实与原件]
  D --> Q[DI / Query / Codex 判断]
```

两份 RMP后/GRT后阶段事实经现有 ORFS 接点进入 DF，通过当前 DI 与 A65 安装版 Query 查询；值、单位、scope 和引用 metadata 的完整字节/SHA通过。原生包25个文件的本机字节与 EF 原件均匹配。阶段数据标明原生估算及诊断用途，不能替代最终 DRT/RCX 的完整 PPA。

八份后续设计/PDK配置在 `var/business/a68-rmp-candidate-admission-20261026/configs/`；只更换新私有源码模板及状态目录，保留 A65 的 Query、PDN/FakeRAM、GCD/Nangate45 500 ps、目标、策略、资源和 PDK。新源码需要测量自己的 baseline，不能继承旧源码指标；旧固化源码重放及历史采用不被热补丁。这些配置仍标为 `long_search_ready=false`。

## 构建过程与 code-check

本轮曾尝试复用 A38 的嵌套缓存，先发现编译数据库仍指向原始 donor，后遇到局部 Makefile 留有 A38 构建路径。RMP对象编译成功，但后续构建失败；这些记录均保留。最终回到现有原生构建器支持的原始 donor 直接 COW 路径，五个 EF 编译/链接任务全部成功，没有给产品构建器加临时兼容层，没有写入旧构建或重启服务。LTO 在同一有效 EF 任务内完成，未因等待重新提交。

新 RMP 静态库成员唯一，归档中的 `Restructure.cpp.o` 与实际新编译对象字节匹配；结合真实候选恢复，排除了“改了源码、链接的仍是旧对象”。

- 原生 C++ 回归应用真实补丁、编译原/新判断，复现2项原VDD/VSS误判，并验证10种修复边界；2项测试/12子项通过。
- Goal全回归 **475 passed / 52 subtests passed**；根相关接点 **23 passed**。根业务 Python 未变，复用 A66 同源码731项全回归。
- 新增测试与验证驱动的 lint、格式、类型检查通过；原生 C++ harness 格式及编译通过。原产品 Python 未变，不借此宣称消除了 A67 已记录的既存严格 lint 债务。
- 源码差异、补丁可逆应用、AST/构建身份、原库/时钟、模块边界及原件逐项核对。26个用户保护文件及 generic_agent、DF/DI在途修改保持。
- 没有模型调用、新服务、数据库或公共 API；完成核查时 EF 五类活动状态均为0。没有调用采用接口。

| Goal 模块改动文件 | 职责 |
|---|---|
| `toolchain/patches/fix-rmp-supply-sequential-admission.patch` | 保存可应用的原生供电误筛修复，仅改变一个判断。 |
| `toolchain/patches/README.md` | 记录基线哈希、应用边界和构建/验证方法。 |
| `tests/unit/test_rmp_supply_admission_patch.py` | 应用真实补丁、编译原/新判断并检查拓扑边界。 |
| `tests/fixtures/rmp_original_sequential_predicate.cc` | 保留原判断，用于复现误判，保留原版权。 |
| `tests/fixtures/rmp_signal_guard_harness.cc` | 构造供电、数据、时钟及混合连接的 C++ 回归输入。 |

根改动为 gitlink、来源manifest和本报告/状态文档；运行材料留在var。

证据目录 `var/business/a68-rmp-candidate-admission-20261026/`，重点为 `code-check.json`、`source-repair.json`、`built-binary.json`、`fact-verification.json`、`rollback-verification.json`、`prepared-bindings.json` 和 EF 原始回执。

## 下一步

对 Ariane 的深组合路径使用已修源码做原生重构的单阶段短诊断，核查实际候选、STA 与拒绝原因，再决定后续专业策略和物理接力。不能将本轮准入修复写成 Ariane 已闭合或 Control 优于固定顺序的证据。

Ariane/ASAP7 setup 欠账、Ariane/Nangate45 最终资格、Ibex/Nangate45 完整证明、GCD/Nangate45 500 ps协作及八组双次合格实验仍未完成，总目标保持进行中。

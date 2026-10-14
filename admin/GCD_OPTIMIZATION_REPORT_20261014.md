# GCD 共同条件复测与功耗回收：O1

工程检查点通过，待老板业务验收。根基线 `025d9f6`，分支 `optimize-gcd-20261014`，保留夜间完整协同证据及 26 份既有用户修改。

## 业务效果

从上轮已时序闭合的独立 ECO 分支继续回收功耗，得到可独立重放的新闭合方案：功耗比该 ECO 分支下降约 0.684%，单元面积下降约 0.128%，core/die 占地不变。相对原 ORFS，闭合时序的功耗代价从约 +1.10% 降至 +0.413%。仍未同时满足“时序闭合、功耗不增加”的严格业务条件，保留原 ORFS 默认基准。

另保留功耗与面积更小的中间方案，但它仍有约 9.147ps 的时序缺口，不能作为时序闭合产品。

没有重新启动昂贵源码演化，没有改变两个 Code 原算法、Flow 原评分、ECO 原提示/筛选或公共契约。新增回收由 Codex 经 EF 调用共同 OpenROAD 既有命令完成，不能记成 GoalEvolve 新源码收益或四 Agent 整链路新收益。

## 相同条件下的真实结果

相同镜像/OpenROAD、15 份相同内容哈希的 FF Liberty、同一冻结 SDC、310ps 时钟及相同 I/O 约束、传播时钟、完整详细布线后的 RCX/SPEF。所有行重新读取真实 ODB/SPEF 测量。

| 指标 | 原 ORFS | 上轮独立 ECO | 本轮闭合：50% 回收 | 本轮取舍：100% 回收 |
|---|---:|---:|---:|---:|
| setup TNS（ns） | −0.119970 | 0 | 0 | −0.0809133 |
| worst setup slack（ns） | −0.0415901 | +0.00546260 | +0.00546838 | −0.00914707 |
| 总功耗（W） | 0.00137303770 | 0.00138819916 | 0.00137870840 | 0.00136956642 |
| 单元面积（µm²） | 45.4750 | 45.4750 | 45.4167 | 45.3001 |
| core 面积（µm²） | 61.3089 | 61.3089 | 61.3089 | 61.3089 |
| die 面积（µm²） | 79.0143 | 79.0143 | 79.0143 | 79.0143 |
| hold TNS / slew / cap / 布局违例 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| 完整 DRT 的 DRC | 0 | 0 | 0 | 0 |

取舍方案相对原 ORFS：功耗 −0.253%，单元面积 −0.385%，|TNS| 减少约 32.56%，尚未闭合。闭合方案从空目录重新回收、完整路由、RCX 和共同测量，11 项物理指标逐值一致。

本轮原 ORFS 的 TNS 与夜间记录有约 0.0001ns 差异：统一使用历史 `write_sdc` 序列化约束，虚拟时钟延迟从 36.225ps 舍入为 0.0362ns。全部新候选使用同一冻结文件，这一微小条件差异不混入收益计算。

## 为什么改变优化路线

1. **同名库内容不同。** Flow 与基准的 15 份 FF 库中，`asap7sc7p5t_SIMPLE_RVT_FF_nldm_211120.lib.gz` 的 hash 不同，Flow 内部 nominal 为 0.7V/25°C，基准为 0.77V/0°C；其余 14 份相同。测量脚本读取基准记录的实际库并核对每份 hash。首次使用 Flow 库的 27 次诊断保留，排除在最终收益之外。原生 Flow 的 TT 语义和旧运行副本保持。
2. **24 个候选都未达到原 ORFS 时序。** 共同复测后，原赢家 core 156.939µm²、|TNS| 6.13621ns；紧凑的第一轮 baseline core 53.5378µm²、|TNS| 6.17472ns。不能靠重新排序获得达标结果，也不能拿原 TT/固定 CP0 收益代替 FF/310ps 收益。这些比较没有证明某一参数的唯一因果。
3. **回收估计必须经完整布线检验。** placement 寄生估计下实测 25/50/70/80/90/100% 六组；激进回收重新引入时序缺口。global-routing 估计下另测 50/100% 两组，最终闭合但功耗仍高于基准约 0.5%，未优于所选方案。八组全部完成 DRT+RCX 及电气复测，没有放宽原规则。

## 实际执行与数据流

```mermaid
flowchart LR
  C[Codex选择实验] --> EF[执行底座]
  EF --> R[共同测量或功耗回收]
  R --> P[完整DRT与RCX]
  P --> A[EF产物和资源回执]
  A --> DF[数据底座]
  DF --> Q[SDK与Query]
  Q --> C
```

EDA、路由、测量、事实导出全部通过公开 EF。复用健康的夜间专属服务，未重启服务；导入使用 `POST /snapshots/from-run`。跨模块仅 installed wheel / SDK / HTTP，未读私有服务数据库或注入 sibling 源码。

全部 24 候选有共同指标快照；三个参考分支、三个代表性 Flow 候选、八组回收和独立重放还有 ODB 对象/关系及产物索引。五组有各 20 条采样时序路径，不表示全路径覆盖。其他候选的原始产物可通过 EF 身份取回。

最终公开接口核查：137 个新 EF 任务全部成功终止并取得资源回执；36 份正式共同测量的指标快照逐值核对通过，使用同一 SDC hash 和同一组 Liberty hash。core/die 与电气原指标通过 SDK 的 stage summary 查询，规范化指标通过 metrics 查询；不假设所有原始字段都有规范化指标别名。

Query 实测比较原基准与新闭合方案的 TNS，返回 artifact 引用；关键路径查到最差 +5.468e−12s。Query 提供事实和出处，Codex 判断取舍，没有新评测底座或自动晋升规则。

## 本机可核对证据

证据根：`var/overnight/gcd-20261014/optimization-r1/`。

| 文件 | 内容 |
|---|---|
| `baseline.json` / `library-audit.json` | Git 基线、用户 hash、15 份库的内容和 nominal |
| `qualified-library-measurements.json` | 24 候选共同实测 |
| `power-recovery-measurements.json` / `power-refinement-measurements.json` | 六组 placement 回收 |
| `global-route-recovery-measurements.json` | 两组 global-routing 回收 |
| `replay-acceptance.json` | 独立重放逐值核对 |
| `pool-metric-imports.json` | 候选指标导入 |
| `query-comparison.json` / `query-final-paths.json` | Query 实际证据回答 |
| `acceptance.json` | 全部任务终态、资源、数据逐值核对及用户修改保护 |

闭合方案完整路由 producer：`run-ee03b5328e474b7a89a77a6c1d638d91`；共同测量：`run-7ec5941ed07a4f8e8fdabfddc1b3c650`。

闭合方案数据快照：`gcd-20261014-opt2-power-50-common-{opendb,orfs,timing}`。物理产物在 `handoffs/opt2-power-50-qualified/`，显式单位 SDC、测量与输入身份在 `handoffs/opt2-power-50-common/`，均位于夜间 state 根。实验 Tcl、TaskSpec、资源及产物留在 var，不作为源码发布。

## 文件改动与门禁

| 文件 | 职责与理由 |
|---|---|
| `admin/gcd_common_remeasure.py` | 公开 EF 取回/复测；冻结参考库 hash 和 SDC 单位；只记录事实 |
| `admin/test_gcd_common_remeasure.py` | 验证跨初始单位 SDC、真实功耗总值解析、同名异内容库拒绝冒充基准 |
| 本报告 | 业务效果、条件、限制及证据 |
| `TASKS.md` | O1 工程状态与未达标业务条件 |
| `ARCHITECTURE.md` | 测量环境身份及 native/共同条件边界 |

新增 Python 的 Ruff lint/format、mypy 通过。回归 128 项通过：Toolkit 环境 124 项，Query 环境运行 SDK 依赖的 4 项。初次单环境收集缺依赖，随后按既有独立环境运行完整集合通过，没有改测试规避失败。

差异/边界检查：仅上表五文件，九业务模块与公共接口未改，26 份用户 hash 不变。没有 formal 等价证明，电气/布局检查不等同于 formal。

## 接续点

先保留闭合且面积略降的方案，以及功耗更低但欠约 9ps 的中间方案。下一优化切片从这两个 checkpoint 做受功耗/面积约束的小范围时序动作，并独立完整路由验证。Flow 下一搜索需明确占地边界和共同评价条件，不能直接修改原研究评分或无界扩大芯片；Goal 下一源码轮次需先根据现有电气失败和原 Teacher 复盘定位机制。

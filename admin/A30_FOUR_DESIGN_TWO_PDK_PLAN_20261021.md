# A30：四设计 × 两套 PDK 实验

老板在 2026-10-21 明确调整本轮交付：GCD、Ibex、JPEG、Ariane，分别使用 ASAP7 与 Nangate45；已有 GCD、JPEG 合格结果保留，不再为串联四专业补实验。每组给 baseline、优化后完整 PPA、条件、来源及采用/拒绝原因；选择 GCD 作为详细专业接力案例，沿用已实测的 Goal 接力方式。不要求八组均执行全部专业，也不承诺每组均正收益。

## 顺序与验收

| 切片 | 工作 | 业务交付及验收 | 依赖 |
|---|---|---|---|
| 1 | 保留 ASAP7 已有四案例，Nangate45 四个 ORFS baseline 经 EF 派发 | 八格矩阵有独立来源；现有 GCD/JPEG 不重跑；Ibex 原证明继续 | 已有 A29 结果、共同镜像 |
| 2 | Goal 显式绑定 PDK 路径、技术 LEF 加载顺序及工艺单元检查 | Nangate45 使用真实工艺；原生四 Student/Teacher、目标与晋升逻辑保留 | 1 的工艺资产 |
| 3 | 各新 baseline 经 DF/DI/Query 查询，运行适用 Goal 策略并共同测量 | 真实 baseline→优化候选及完整指标；失败留证据，其余组继续 | 1、2 |
| 4 | 对实际采用候选验证功能；汇总两 PDK 表及一个接力案例 | 不把测量候选写成采用；八组逐组收口，不等单组才推进其他组 | 3 |

## 本切片修改范围

- `chip_evolve/native.py`：Goal 输入目录依据实际平台，现有内部 profile 传递 PDK 与单元表路径。无公共函数签名/API 变化。
- `goalevolve/goalevolve/evaluation/contest2026.py`：读取显式 PDK；技术 LEF 优先；原官方结构检查及观察报表使用该 PDK 单元表；RMP 不把 fakeram 当组合标准单元。
- `goalevolve/third_party/official_checker/validity_check/flipflop_check.py`：识别 Nangate45 的 CK 和扫描 DFF；保留原 CLK/DFF 行为及原署名。时钟错接/删除状态负例必须拒绝。
- 两份对应测试：工艺绑定、原 ASAP7 行为、负例回归。
- `SOURCE_MANIFEST.json`、任务/架构/本计划：记录实际实现版本和待完成实验，不以编译通过代替 PPA 验收。
- `var/business/a30-four-design-two-pdk-20261021/`：本轮部署配置、冻结输入、EF 回执、操作日志与结果。不修改历史 A29 实验或用户未提交文件。

## 实际派发（非成功声明）

2026-10-21 已从共同镜像经 EF 核实工艺和设计配置，读取任务 `run-c5ed621bbc8f432a9e525cf2d9d5892c` 成功。Nangate45 baseline：GCD `run-a3b63484b71141699d2902b13c14f72f`；Ibex `run-58121507177d49af92721ea1d74b6453`；JPEG `run-e1f725eda4f34f05b084771cbb3a7288`；Ariane `run-b2a9b2fe65484a01b9588570b81be79b`。实际资源容量由 EF 查询，本轮为 32 GiB；不依据旧配置里的历史 128 GiB 更改服务。

Nangate45 使用镜像官方设计约束：GCD 0.25 ns、Ibex 2.2 ns、JPEG 1.0 ns、Ariane136 6.0 ns；各组 baseline/候选同约束。不同 PDK 只分别比较组内收益，不把跨 PDK 绝对值解释成优化收益。Ariane 的 Nangate45 ORFS ariane136 RTL+fakeram 与既有 ASAP7 研究提供的映射网表+固定宏地板规划分别标注，不能声称两者输入逐字节相同或构成严格跨工艺受控实验。

## 数据流与结果表达

```mermaid
flowchart LR
  C[Codex] --> E[EF 执行 ORFS baseline]
  E --> D[DF 解析和登记]
  D --> I[DI / Query 查询诊断]
  I --> G[Goal 原生优化]
  G --> E2[EF 构建及运行候选]
  E2 --> D2[DF / DI 最终事实]
  D2 --> C2[Codex 比较与选择]
```

每行记录 PDK、设计/源版本、角/时钟、功耗、实例/core/die 面积、setup/hold WS/TNS、电气/布局/布线违反、父子产物及功能验证状态。结构检查不是完整逻辑证明。单元表按真实标准单元各自一个 singleton，仅识别可移动标准单元，不伪造跨单元等价关系；宏保持固定。

## 实际进展与新增单位适配（约 17:00）

- Nangate45 GCD 与 Ibex ORFS baseline 已完整交付，各 12 值/3 范围公共 DI 核验通过；两份 Query 诊断完成。GCD 6.3340640627 mW/943.502 µm²/setup WS −0.161583 ns/TNS −7.08646 ns；Ibex 22.098418325 mW/29473.1 µm²/setup WS −0.00995204 ns/TNS −0.210899 ns/cap3。不是合格采用结果。
- 两个 Goal 原生环境已实际运行，构建、流程、解析、布局及原结构 4/4 检查通过；尚无四 Student 的完成结果。真实 CSV 暴露 Nangate45 功耗单位为 nW，而 native 字段默认 pW，补原生读数归一化及六单位回归。ASAP7 pW 原行为保持。
- 因明确单位错误，两个刚启动的原生前端 r1 在尚无 Student CPP 结果时退役，EF 无活动专业任务需要取消，保留原生 baseline/Teacher 尝试及成本；同 ORFS baseline 和 Query 以修复版新 r2 继续，不重跑四组 ORFS，也不触碰旧 Ibex 证明或既有采用结果。其余两组自动接续使用修复版。
- 工程检查：根 581 项通过；Goal 原全套 487 项中 483 通过、3 条件跳过、1 本机 HTTP 代理环境失败，正确 NO_PROXY 下同项通过。随后单位修复的 unit 全套 473 项中 470 通过、3 条件跳过。两次类型检查零错误，相关 lint/diff 检查通过；26 保护文件保持。
- [八组追踪表](A30_EXPERIMENT_MATRIX_20261021.csv)区分已采用、待证明、负结果与新 baseline，不把空数据填成零。

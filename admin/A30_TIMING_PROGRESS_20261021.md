# A30 时序效果核查（2026-10-21 晚间）

时序数据一直逐节点保存；此前口头汇报偏重功耗和面积，不能由此省略时序代价。当前已采用的 ASAP7 GCD、JPEG 支持的是固定时钟下的功耗面积优化，并非已证明的频率提升。WS 是最差 slack；WNS = min(0, WS)，正 WS 不应称为正 WNS。TNS 的单位为 ns，以下 WS 单位为 ps。

| ASAP7 设计 | 固定周期 ps | 基准 setup WS | 最终/候选 setup WS | setup TNS | hold TNS | 状态 |
|---|---:|---:|---:|---:|---:|---|
| GCD G02 | 310 | 9.34292 | 0.0834055 | 0 | 0 | 已采用；余量变小 |
| GCD DPL→Goal DG1 | 310 | 9.34292 | 1.31586 | 0 | 0 | 已验证替代路径；仍保留 G02 |
| JPEG JP3 | 545 | 19.5042 | 10.2303 | 0 | 0 | 已采用；余量变小 |
| Ibex IP3 | 900 | 25.478 | 10.1494 | 0 | 0 | 物理可行，完整功能证明超时，未采用 |
| Ariane AG4 | 900 | -285.396 | -391.727 | -310.3 | -24.7916 | 恶化、拒绝；基准本身亦不闭合 |

实际接力的时序修复：JPEG JG3 setup WS -12.5853 ps / TNS -0.0701142 ns，经原生 VT/size 收尾后 JP3 达到 WS 10.2303 ps / TNS 0；这是时序恢复，不是相对原始基准加速。GCD G03→ECO→路由补全，setup TNS 从 -0.856145 ns 改善至 -0.266838 ns，违例量减少约 69%，仍失败，不采用。负分支全部保留。

G02 与 DG1 各自已有两次独立固定 Goal 动作及最终测量，结果分别同值，含 setup/hold TNS 0。该重复覆盖的是单棒动作，不冒充前序 Flow 搜索或完整 DPL→Goal 链重复两次。两对网表均与既有已证明原件逐字节一致。原值和均值位于 A30 `paired-summary-gcd-asap7-{g02,dg1}/two-trial-summary.json`。

Nangate45 已有基准：GCD 250 ps，WS -161.583 ps / TNS -7.08646 ns；Ibex 2200 ps，WS -9.95204 ps / TNS -0.210899 ns；JPEG 1000 ps，WS -108.898 ps / TNS -37.5624 ns。优化和 Ariane 原基准仍待实际交付，不能算通过。八组合格、两次完整链及平均值尚未齐全。

## 实际发现并修正的新增 Flow 阻断

新增 Nangate45 完整 Yosys 来源试次 `run-c57f209b4890426094d611743eb33ec0` 失败。公开 EF 原件显示，输入 SDC 使用 ps，但 ORFS `write_sdc` 在 `1_synth.sdc` 中保留数字 250、70、50 并省略单位；下一 Nangate45 进程按 ns 读取，CTS 出现约 19.8 ns hold 债务、插入 123 buffers 后报 RSZ-0060。这是跨阶段单位丢失，不是实际 250 ps 下的优化结论。

改动范围及数据流：

- `chip_evolve/clock.py`：内部 Flow 时钟绑定支持显式原生 ps/ns；周期与 IO、latency 保持同一单位。
- `chip_evolve/professional.py`：根据专业原生平台单位绑定可调时钟，ASAP7 ps、Nangate45 ns，与既有 Flow leaf 的解释一致。
- `chip_evolve/flow_recipe.py`：来源必须匹配原生平台单位；ns 来源显式提供 `ABC_CLOCK_PERIOD_IN_PS`，使综合目标与物理目标一致，不再强迫所有平台使用 ps 输入。
- `admin/test_flow_recipe.py`、`admin/test_local_business.py`：覆盖两 PDK 的原始输入继承、时钟/IO保留及错误单位，避免后续测量 SDC 替换原来源。

私有修正配置将原 56 个时间数值按 1000 倍精确换算为 ns，物理周期仍 0.25 ns、IO 0.05 ns、虚拟时钟 latency 0.07 ns；ABC 的 make 绑定按实际候选周期动态转 ps，保留调参能力。重新登记完整来源的独立基准和两次原生 1×50 搜索，不混用旧 family 目标、失败试次或基准；旧任务、原约束和全部历史原件保留。没有改模型、评分、专业算法、公共 API、服务或容量。

针对回归 51 项通过，根现有回归 607 项通过，Ruff/格式及 Pyright 0 错误。26 份用户保护文件哈希保持。真实修正分支的综合周期、阶段 SDC、最终 PPA 和原生搜索仍须实际核验；测试通过不是八组实验通过。

完整逐节点原件索引与时序列：`var/business/a30-four-design-two-pdk-20261021/delivery-latest/relay-nodes.csv`。修正依据、配置与失败公开原件：同目录 `gcd-nangate-flow-unit-loss-correction.json`、`gcd-full-source-first-failure/`。不使用这些混合路径组 slack 推算 Fmax。

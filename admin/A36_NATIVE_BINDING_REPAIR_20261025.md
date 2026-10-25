# A36：四专业运行绑定与 DPL 短验证

基线 `f937938`。本轮延续“具体诊断→定点修复→短验证→code-check”，没有启动专业长搜索或完整 EQY 证明，没有改服务/容量/历史任务。

## 发现并处理的阻断

八份 A35 私有配置的解释器、库、SDC、依赖、专业源码/模板、源码 seed 和 core binary 路径已核对。四份 Nangate45 配置均缺少 `dpl_case`，会在 `prepare_case` 读取时失败；ASAP7 四份已有该字段。只在 A36 新配置中显式补齐原生问题模板：

| 实际设计 | 原生模板 | 注册后的实际设计 |
|---|---|---|
| GCD/Nangate45 | `gcd_nangate45` | gcd |
| Ibex/Nangate45 | `ibex_nangate45` | ibex |
| JPEG/Nangate45 | `jpeg_nangate45` | jpeg |
| Ariane/Nangate45 | `ariane133_nangate45` | ariane136 |

模板只复用原研究的算法/patch surface/目标/输入阶段；已有 `prepare_case` 显式改写设计名、PDK 和 ORFS 配置。八份实际注册均核对通过，`input_stage` 之后的完整算法声明逐字节保持。没有伪装 Ariane133 为实际运行设计。

Goal 模板中的历史 `design` 名也做了检查：原接入层会用实际 top 重写该字段；目标值/权重需按策略理解，不能仅因文件名来自另一设计就误判功能错误。本轮没有擅改专业权重、目标或评分。

## DPL 的真实短验证

EF `run-d3e32e96004041ea9ff1e06b568b8c47` 使用已核 SHA 与 build receipt 的 DPL 共同版本 core binary，读取原 GCD/Nangate45 ORFS 归档唯一 `3_4_place_resized.odb`，在新 500 ps **诊断**时钟下分别运行三条原始命令链：

| 原始路径 | 动作 | 原生日志最终 HPWL（µm） | 执行/布局检查 |
|---|---|---:|---|
| Diamond | detailed placement → improve(seed1) → mirroring | 3206.7 | 通过 |
| negotiation | 同上，新版默认 negotiation | 3142.1 | 通过 |
| evolve | 原 `*_evolve` 三动作 | 3116.3 | 通过 |

三条链各自从同一原布局输入开始，输出 ODB 与日志由 EF 登记；源设计 scope 先经 DF/DI 核验。没有 Teacher/Student、源码搜索、CTS/route、完整新基线、最终 PPA 或采用。这里验证命令兼容性/入口/阶段合法性，不将这些 HPWL 作为新协同收益。

探针最初将 SWIG `Clock.period` 的原始秒值误按 ns 字符串判断；三条原工具链本已 exit0。收取端按原始秒值转换为 ps 后均为 500，保留原日志/原断言失败与新解释收据，**未重新运行已完成 EDA**。A34 使用 `sta::time_sta_ui` 的时钟加载证据保持独立有效。

## Ibex/Nangate45 证明的结论

公开 EF 确认 `run-010c1023e6514e99911eb866bdcbe4ae` 是 1800 秒超时。原分区列表共 19384，保留的 strategy status 中 5333 为 PASS；没有整体 PASS，不是 A31 已修的成功收尾误判。EF 该次记录峰值约 1.29 GiB、CPU 1341.07 秒、22 进程，不能把失败归因于已证实的内存不足。

下一次新配置将已有 `validation.equivalence_seconds` 从1800改为14400，匹配先前已验证的显式大任务预算入口；原 PDR、Liberty、solver、状态/时钟、job 数、内存与覆盖政策保持。这里只准备合理时限，不据此宣称证明完成，也未在审计期间重启全场计算。旧部分成果和超时证据保留。

## 门禁、文件和接续

- 唯一测试源码修改：`admin/test_dpl_design_binding.py`，把既有四设计注册用例扩展到 ASAP7/Nangate45，验证实际 registry 字段与原算法尾部保持。
- 针对性 18 测试及根业务 **658 测试通过**；Ruff、格式、Pyright、差异检查通过。26 个用户保护文件 SHA 保持，无模块内部访问、新服务/API/数据库或跨源码路径。
- 新私有配置与真实证据位于 `var/business/a36-native-bindings-20261025/`：`runtime-binding-repairs.json`、`initial-path-audit.json`、`dpl-stage-short-check-final.json`、`protected-file-check.json` 及检查日志。私有配置不提交 Git；本报告、TASKS/STATUS 维护续接说明。
- 如要改变 DPL 的模板选择，在下一轮明确的设计配置中改 `dpl_case`；不要给平台添加隐藏猜测或改变原研究算法。完整 GCD 500 ps 基线/协作、Ibex 完整证明、八组双次 PPA 仍未完成。

长搜索继续暂停；后续核查执行产物到数据底座的新状态交付，以及尚未覆盖的具体业务阻断。

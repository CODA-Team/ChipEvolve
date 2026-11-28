# A46：恢复原生变量时钟的 Flow 接入

接续 A45 根提交 `c72c8a0`。本切片只修真实来源的接入阻断，长专业搜索保持暂停，不改公共接口、算法、参数域或历史结果。

## 具体问题与修复

A45 已由完整 ORFS 成功加载的 GCD/Nangate45 500ps SDC，被两处封装文本假设拒绝：来源准备要求单位声明在文件首行，时钟绑定只接受数字字面量。原件前有注释，物理与虚拟时钟都使用原生 `clk_period` 变量。

`chip_evolve/clock.py` 增加原生单位读取，并识别已知单周期/单物理端口模板及其匹配虚拟时钟；已识别模板逐字节返回，保留动态 I/O 表达式。`chip_evolve/flow_recipe.py` 复用单位读取，接受注释/空行后的显式单位。沿用已有 AES 原生时钟适配含义；不解释任意 Tcl，不转换单位，不修改周期或 I/O 比例。

## 验证结果

- 修复前：实际原件复现两个阻断；相关测试12失败/27通过。
- 修复后：53项针对检查、706项根业务回归通过；Ruff、格式、Pyright及差异检查通过。
- 真实 Tcl 检查：周期从0.5改为0.8时，物理/虚拟时钟同步，输入输出延迟仍为周期20%。不匹配周期/虚拟时钟/端口/单位反例拒绝。
- 实际来源准备复用既有 EF，三个任务全部成功：`run-e542d941a2b84aaf87c08b762cf6d35c`、`run-bf2427169d304e8db24963bf2c57ea06`、`run-8494fd0625944513bb2deca797196a29`。
- 实际 Make 展开确认 Yosys `SYNTH_USE_SYN=0`、完整17项基线参数、ABC500ps、hierarchical0/flatten1；准备的SDC与批准原件SHA完全相同。
- 26个用户保护文件、A45结果及原SDC、来源准备时产品代码SHA保持；原EF/DF服务未调整，收尾EF活跃队列为空，容量仍32CPU/32GiB。

本切片是来源准备资格，不是完整Flow搜索资格；`native_search_qualified`仍为false。无模型、专业优化或新PPA，A45单次基线不改成双次均值。

## 差异审查与架构约束

| 文件 | 职责及影响 |
|---|---|
| `chip_evolve/clock.py` | 已有Flow时钟接入的局部兼容修复；原生模板保留原字节 |
| `chip_evolve/flow_recipe.py` | 来源准备复用同一单位判断，仍从原注册来源读取 |
| `admin/test_native_flow_clock_template.py` | 原生模板、真实Tcl动态I/O及错误绑定回归 |
| `admin/test_flow_recipe.py` | 来源单位/ABC既有检查增加前导注释用例 |
| 本报告、`TASKS.md`、`admin/STATUS.md` | 记录实现检查点和未完成边界 |

跨模块仍走原 EF/DF/DI，没有新服务、公共API、数据库或跨源码导入。若要调整此类输入兼容行为，改 `clock.py` 的模板识别即可，不改研究策略。

证据位于 `var/business/a46-native-variable-clock-20261025/`：`actual-blockers-before.json`、`test-before.log`、`targeted-regression.log`、`root-regression.log`、三项静态日志、`actual-source-prepared.json`、`final-code-check.json`。工程检查通过，待老板业务验收；八组双次协作结果尚未完整交付。

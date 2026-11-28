# A79：修复 ECO 过程 QoR 的功耗缓存与时间戳阻断

根基线 `a89e357`、ECO 基线 `04a17a8`。模块修复 `0105684` 已发布到 ChipEvolve 的 `modules/timing-eco-agent`；新会话从正式模块冻结源码，旧会话和历史结果不热修改。工程检查通过，老板业务验收独立。本轮没有专业模型搜索、优化动作或新采用结果。

## 具体问题与修复

沿 A78 发现的 STA 功耗缓存问题核查原 ECO：`run_loop` 每次 ECO 后执行 GRT/寄生更新，再在持久进程调用 `dump_iter_qor`；该 helper 直接 `report_power`，没有刷新缓存。因此过程功耗 CSV 可能仍表示前一个 RC 状态。原最终物理资格由独立测量完成，不能把本次过程记录缺陷等同于最终 PPA 全部失效；旧 ECO 的 GRT 迭代功耗也不能未经核对直接作为逐棒收益。

真实共同 OpenROAD 还复现同一 helper 的时间戳错误：`clock format [clock seconds]` 触发 `invalid command name :Tcl/Localtime`；显式设置 UTC 仍触发同类错误。两个失败 EF 原件保持。修复直接记录 epoch 秒数，避免为无关紧要的报告注释加载格式化/时区模块，没有吞掉真正的指标错误。

仅修改两个模块文件：

| 文件 | 职责及影响 |
|---|---|
| `src/main_orch.py` | `dump_iter_qor` 的平台 EF 会话在报告功耗前使用与原 Goal 一致的活动 set/unset 刷新，恢复当前平台原生默认活动模型；独立原生模式的活动设置保持。时间戳改为 epoch 秒。 |
| `src/test_qor_power_cache.py` | 4 项针对回归：连续 RC 更新后的新鲜功耗、原生独立模式、刷新失败不伪报旧功耗、无格式化库时报告仍完整。 |

没有改原专业动作、提示词、评分权重、WNS 最佳选择和回溯规则。AST核对所有原 Python 函数、类及其余顶层节点完全相同，仅 `NODE_NET_TCL_BLOCK` 常量变化。Ruff要求的字符串引号变化不改变 Tcl 内容。未增加服务、公共 API、数据结构、数据库或跨模块源码依赖。

## 实际原生配对，而非仅 stub 测试

两组相同 A77 保存 ODB、Nangate45 库、6ns SDC、共同镜像和 GRT，均为只读报告，没有设计动作。控制组只修时间戳，保留旧功耗行为；修复组另补刷新，二者 helper 内容仅相差刷新块。依次 placement RC → GRT → 独立再次刷新，并由实际 `parse_iter_qor` 解析生成文件。

| 实际 helper | placement 首读 W | 切换 GRT 后 W | 再独立刷新 W | 结论 |
|---|---:|---:|---:|---|
| 控制组，旧功耗逻辑 | 0.158 | 0.158 | 0.160 | GRT 首读错误沿用旧缓存 |
| 修复组 | 0.158 | 0.160 | 0.160 | 与独立刷新一致 |

保留原 ECO 默认报告精度，不把这些三位数当作精确优化幅度。12位补充报告 power 为 **0.1604765951633 W**，与 A78 同保存状态独立刷新一致；这是测量纠正，不是优化收益。各阶段两组四项 setup/hold WS/TNS 精确相同，面积也相同。

控制 EF `run-585a2524583b436e9d7d8ef9a964e4d3`，CPU61.24秒、峰值2359873536字节；修复 EF `run-33a5e4cf1da241e38497b584fb6f4a4c`，CPU77.36秒、峰值2365317120字节。各2CPU/8GiB/300秒；8份捕获原件由公开 EF bundle/manifest 校验，源 ODB/SDC/库/helper/脚本哈希保持。原时间戳失败 run `run-ccf42c8bdce64fc69bfa75984927aae4`、UTC尝试 `run-5789fed928624594883ba489392f7281` 均保留，不隐藏为成功试次。

## 统一事实链与 code-check

修复后观察经既有 ORFS metadata adapter → EF → DF → DI → 独立安装 Query；快照 `a79-run-33a5e4cf1da241e38497b584fb6f4a4c-ECO-fresh-power` 包含 RC/精度/非最终 PPA 语义、控制组、修复组与原件引用。7项原始字段同值，Query准确回答0.1604765951633W，引用的 metadata完整字节/SHA核验通过。

- 新测试在旧源码复现2失败/1通过，修复后4项通过；时间戳另由两个真实失败和修复后成功验证。
- ECO全模块 **46 passed / 2 subtests passed**，根业务接点 **54 passed**；根产品源码保持，复用相同源码的 **740项**完整回归。
- 两产品文件与三私有脚本 Ruff/Pyright通过，改动常量区域及新测试/驱动格式检查通过，Git差异审查通过。
- 26份用户文件、DF/DI在途修改和生产服务保持；所有EDA诊断经EF，事实经公共DF/DI/Query，未打开私有数据库或新建服务。

证据目录 `var/business/a79-eco-power-cache-20261026/`：`native-evidence-verification.json`、`source-boundary-review.json`、`fact-verification.json`、`code-check.json`、门禁日志及`continuation.json`。

此切片解决“过程数据是否对应当前状态”与“报告是否能实际生成”，不代表 Ariane 已满足原电气/功耗约束。长专业搜索仍暂停。下一项针对已经测到的大设计 DF 交付耗时做具体阶段定位，保留用户在途实现，不为性能猜测重构平台；其余八组双次与设计资格缺口仍在。

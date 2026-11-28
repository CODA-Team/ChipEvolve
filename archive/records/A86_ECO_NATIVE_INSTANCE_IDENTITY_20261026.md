# A86：修复 ECO 的 STA 显示名与 OpenDB 实例身份接续

根基线 `e4af3f6`、ECO 基线 `0105684`。**实际故障已复现，定点修复与短验证通过。** ECO 修复提交 `ff8d13c`，未来会话使用新冻结副本；没有修改活动或历史会话，没有恢复长专业搜索。

## 问题与业务影响

时序报告给出的寄存器名 `issue_stage_i.i_issue_read_operands/fu_data_o[100]$_DFF_PN0_`，在 OpenDB 中用含转义字符的名称保存。原 ECO 的克隆、扇出查询及两类路径邻居导出直接 `findInst`，会把真实存在的报告对象当作不存在或跳过。

同一 Ariane/Nangate45 最终 ODB/SPEF、6ns SDC、typical 库及共同 OpenROAD，实际原生只读复现如下：

| 查询 | 原实现 | 修复后 |
|---|---|---|
| OpenDB 原始名称 | 五个负载正常返回 | 五个负载、顺序和 slack 全保持 |
| STA 显示名称 | instance not found | 与原始名称结果精确相同 |

这个问题阻断的是“Agent 按报告名称开展调查和动作”，不表示原模型策略、全部原生 ECO 或历史最终 PPA 均失效。

## 修改范围与数据流

只改两个模块文件：

| 文件 | 职责 |
|---|---|
| `OpenROAD_utils/eco_procs.tcl` | 内部 `_eco_find_dbinst` 优先保留原始 OpenDB 精确查找，失败后通过唯一 STA cell 对象转回 OpenDB；接入原有五处实例查找，同一实例排除改用对象比较。 |
| `src/test_native_instance_identity.py` | 四个回归覆盖显示名/原始名同结果、克隆进入原生动作、缺失/歧义拒绝、精确名称不依赖 STA 匹配。 |

数据流：模型/时序报告名称 → 原始 DB 查找或唯一 STA 实例 → 原生 OpenDB 对象 → 原有扇出排序、邻居调查或克隆动作。公共函数签名、参数、返回结构不变，无新增公共 API、服务、数据库或跨源码依赖。

逐个 Tcl procedure 比较确认：仅新增一个内部 helper；四个原过程只变实例定位及同对象判断，其余所有过程体和原函数参数保持。原动作、评分、提示、选择、回溯和路由校准保持。要改名称定位查 helper；要改专业动作仍查原对应过程，不在平台派发层拼接或剥除名称转义。

## 真实短验证与纠错记录

全部 EDA 通过现有 EF，1 CPU/4 GiB/120秒预算，无模型调用。修复后不只看函数返回：在一次性内存副本实际克隆原寄存器，验证移动负载与克隆输出是同一 native net、与原输出分离，D/RN/CK 三输入网络保持，实例/网络数恰好各增加一个。该动作只验证连接机械能力，**不签署功能等价、物理合法或 PPA 改善，也不采用这个副本**。

| 原生记录 | EF run | 结论 |
|---|---|---|
| 原实现读名称 | `run-32ab5bca6c434deba561150648b5d9cc` | 显示名失败，原始名成功，复现成立 |
| 首次修复验证 | `run-e2bf4b13c13d4be78279114f73ad30b2` | 排序同值，克隆返回成功，但验证器错误假定新网名称固定，保留失败 |
| 名称诊断 | `run-9b0a7ce1c0b84b37bcc6a3bac4a6b4bd` | 原生 make_net 自动追加唯一后缀；记录实际对象，不作为最终连接验证 |
| 实际对象最终核对 | `run-5710895ceeaf4452bba2b71db4191822` | 排序、输入与输出实际连接、对象增量全部通过 |

最终验证改为比较真实网络对象，没有因此修改原克隆算法；不把诊断轮误写成完整通过。原最终源文件 SHA 保持，前后两次签收共四份 EF 捕获文件及原日志 SHA 核验通过。

## code-check、发布与剩余问题

新回归在旧实现 **2失败/2通过**，修复后 **4通过**；ECO 全模块 **50通过/2子项通过**，根接点 **57通过**。新 Python 测试 lint、格式和类型检查通过，实际 Tcl 解析/原生调用通过；根产品源码未改，复用 A82 同源 **754项根回归**，不是本轮重跑。差异逐文件核对，26份用户保护文件、`generic_agent.py`、DF/DI在途修改保持。

模块提交到 ChipEvolve 的 `modules/timing-eco-agent`，不推第三方 origin。根只更新模块 gitlink、manifest 的 ECO commit/tree、本报告、STATUS、A54、TASKS及 ARCHITECTURE；上游来源与署名保持。

证据目录 `var/business/a86-eco-native-instance-identity-20261026/`：各原生 preflight/execution/log、`native-evidence-verification.json`、`source-boundary-review.json`、`check-results.json`、`code-check.json`、`continuation.json`。工程检查通过，老板业务验收独立。

本切片关闭已复现的公共 ECO 对象定位阻断。A85 的 Ariane/Nangate45 电气不合格、Ariane/ASAP7 setup、GCD/Nangate45 500ps协作、八组双次及大库实际导出/写入延迟仍未关闭，不将这个功能修复计为新增论文优化结果。下一项按 A54 核查尚未通过的实际接口/环境阻断，继续先复现、定点改、短验证，不恢复长搜索。

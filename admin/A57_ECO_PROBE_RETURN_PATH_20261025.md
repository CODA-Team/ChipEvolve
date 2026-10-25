# A57：修复 ECO 已查到网络却未交给下一轮模型

基线根 `c63b47d`、ECO `f0f218e`。接续 A56，只处理专业探针的信息回传缺陷；不改变专业算法、动作、评分、迭代预算、公共接口或最终采用规则。长优化/模型搜索继续暂停。ECO 检查点 `163120b` 已发布到 ChipEvolve 的 `modules/timing-eco-agent`；根 gitlink/manifest 固定同一提交。

## 具体阻断与修改

原生 `eco_net_sink_report` 把网络、PIN/PORT、方向及 master 打印在 OpenROAD stdout，却没有返回值；原生收集器只读取返回值，因而给下一轮模型写入 `(no rows returned)`。即便补上返回值，收集器还会把每行裁成前两列，丢掉方向/master。问题位于专业查询的最后一段交付，不是设计中没有数据。

| 文件 | 修改职责 |
|---|---|
| `timing-eco-agent/OpenROAD_utils/eco_procs.tcl` | 保留已有 stdout，另返回完整网络标题及排序后的端点行。 |
| `timing-eco-agent/src/main_orch.py` | 原探针收集器逐行保留全部返回内容；原两列 slack 查询、错误与空结果处理继续使用。 |
| `timing-eco-agent/src/test_native_probe.py` | 新增真实 Tcl 过程、实际源码收集器及原 `build_prompt` 的回归；覆盖总线名称、PIN/PORT、两列查询及原生错误。 |

不新增服务、查询框架或模型循环。EF 仍拥有原生 OpenROAD 会话及其子进程；跨专业设计事实仍走 DF/DI/Query。旧会话副本不热改，第三方来源与署名保持。

## 针对性短验证

修复前新增用例 **2 failed / 2 passed**，直接复现缺少返回值及收集器信息丢失；修复后 **4 passed**。测试执行实际 Tcl 过程与从原生脚本提取的收集器，并调用原有 `LLM_call.build_prompt`；没有调用模型。

通过 EF 对同一份 Ariane/ASAP7 已登记 ODB、21 份库和同一个命令进行只读前后对照，任务 `run-bdad408d5edb4b94b89fc8f973897629` 成功。查询 `_255074_/Y` 所在网络，旧版仍得到“无返回行”，修复后得到：

```text
NET _094635_ terminals=6
PIN _255074_/Y direction=OUTPUT master=AO31x2_ASAP7_75t_SL
PIN _255579_/A2 direction=INPUT master=AO222x2_ASAP7_75t_SL
PIN place57107/A direction=INPUT master=BUFx6f_ASAP7_75t_SL
PIN place57108/A direction=INPUT master=BUFx6f_ASAP7_75t_SL
PIN place57113/A direction=INPUT master=BUFx6f_ASAP7_75t_SL
PIN rebuffer72403/A direction=INPUT master=BUFx3_ASAP7_75t_SL
```

原 ODB SHA 保持，公共 EF 产物及实际执行的 helper/collector 已取回核 SHA。原会话 helper 与该会话冻结 profile 的哈希一致。最终源码与已执行收集器相比仅有注释和等价表达式空白变化，实际 Tcl 命令一致。没有执行 ECO 动作、GRT/DRT、PPA 测量或功能证明。

使用已安装 DI SDK，在精确原快照 `local-run-3792ba19f8124d4e845399234640011a-opendb` 查询 `_094635_`，6 个端点的名称、方向及父单元 master 与原生查询一致，driver=1、fanout=5。**原 DF 响应仍为 truncated**，缺少部分关系、routing/evidence；本次仅核对这六项完整端点，不能据此宣称全部上下文完整。

把真实新探针字节交给隔离路径中的原生 `build_prompt`，下一轮 `<probe_responses>` 内确实包含完整结果。只验证原生提示词构造，没有新建 harness 或模型调用，也不证明新一轮 ECO 有收益。

## code-check 与回归

- 两份修改 Python 文件 Ruff 通过；Pyright **0 errors / 0 warnings**。测试文件整文件格式通过，大型上游脚本仅对实际修改范围检查格式。
- ECO 模块 **37 passed / 2 subtests passed**；根业务 `pytest -q admin/test_*.py` **712 passed**。
- 三文件逐项 diff 与 `git diff --check` 通过；无跨项目源码导入、公共契约、数据库或服务更改。
- 26 个用户保护文件哈希保持；EF 五类活动状态均零。没有待恢复的新长任务。

证据：`var/business/a57-eco-probe-return-path-20261025/`，包含 before/after 测试、全部门禁日志、真实 EF 执行/原件核验、DF 同网查询及精确范围说明、原生下一轮提示词和最终检查。私有驱动的 lint/format/type 也通过，运行文件不提交。

## 业务效果与接续

ECO 提问“这个网络连接了哪些单元”后，现在能够收到已有设计的完整端点信息，继续原有推理；不再把实际查询成功误报为空。修复的是信息交付能力，尚未生成新的合格 PPA 或完整 ECO 轮次。

改变探针的事实字段应修改 Tcl helper；改变下一轮如何接收应修改原生收集器；专业策略仍留在原项目。下一项核查 Ibex/Nangate45 完整证明的具体困难义务与配置，先诊断/有界验证，不直接重启四小时证明。总目标仍进行中。

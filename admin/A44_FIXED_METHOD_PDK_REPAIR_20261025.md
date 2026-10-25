# A44：固定方法重放与物理对照继承原 PDK

基线 `90a5670`。本轮处理文档化辅助入口的工艺选择，不启动长搜索、模型、证明或新物理计算，不修改冻结历史。

`chip_evolve.comparisons.replay_goal` 和 `admin/goal_route_control.run` 均将共同交付工艺固定为 `inputs/asap7`。旧 ASAP7 标准目录碰巧可用；Nangate45 或其他明确冻结目录会选错。它们不是八组优化的唯一入口，但属于承诺可用的固定方法/物理控制功能，不能遗漏。

## 实现与文件

- `chip_evolve/comparisons.py`：重放保持原命令、二进制和 Tcl，只在 qualify 时优先使用原 profile 的 `pdk_root`；旧 profile 按其 state_root 与明确设计平台定位。
- `admin/goal_route_control.py`：保留原修复动作移除规则、二进制前后检查与交付恢复，只将 checkpoint 的 PDK 选择改为原冻结路径；旧无 profile 记录按明确平台定位。
- `admin/test_fixed_goal_replay_pdk.py`：覆盖两 PDK/显式冻结与旧目录，检查原输入、线程、修复动作及程序内容保留，输出只重定位到新目录。
- `admin/test_goal_route_control.py`：扩展原物理控制测试，确认只移除原允许动作，PDK路径继承，不改源文件。

未增加公共参数、通用适配层、服务、数据库、评分规则或新的调度策略。需要改变新任务的工艺位置时，配置该任务 profile 的 `pdk_root`；已有记录仍按自身冻结来源解释。

## 短验证与 code-check

修改前两入口共6例失败/7例通过，修改后 **25 项针对性检查、689 项根业务回归通过**；四文件 Ruff、格式、Pyright、diff 检查通过。客户端实际 `python -m chip_evolve.comparisons --help` 可加载原命令。

真实冻结来源核查覆盖：

| 来源 | 原生 baseline EF run | 本轮检查 |
|---|---|---|
| GCD/ASAP7 `goal-native-reference` | `run-0b988f57007046429f2c039edc578ad7` | 旧目录定位与原 Tcl `source setRC.tcl` 一致 |
| GCD/Nangate45 `a30-gcd-nangate45-goal-r2` 中的 baseline | `run-986844a2c8194b82917f55cb889f002c` | 显式 pdk_root 与原 Tcl 相同，不误取 ASAP7 |

两份原 baseline 的公开 EF 终态实际均为 succeeded；所选 `setRC.tcl` 和 `rcx_patterns.rules` 的 SHA 与原请求中的 inputs 逐项一致。物理控制的 `without_repairs` AST 未变，26个用户保护文件保持。这里核查已执行来源及工艺字节，不冒充新的 Nangate45 完整 matched replay、消融或 PPA 收益。

证据：`var/business/a44-fixed-method-pdk-20261025/actual-pdk-binding.json`、`test-before.log`、`targeted-regression.log`、`root-regression.log`、`business-help.log` 和静态日志。最初补丁上下文不匹配发生在修改前，重新读取真实代码后修正，未影响运行任务。

原完整基线/优化/证明/双次结果仍按各自业务阶段验收。当前辅助工艺选择阻断收口，长优化搜索保持暂停；下一步在不做源码搜索的前提下核查已批准 GCD/Nangate45 500ps 新条件的完整物理来源。

# A39：让新 Goal 任务真正消费已修源码

基线根 `4606f36`、Goal `d41efa2`。本轮解决接入层源码与构建 donor 的实际绑定，不启动专业搜索，不更改算法、目标、评分、资源预算、公共接口或历史实验。

## 找到的具体阻断

1. 七份 A36 私有任务模板仍指向旧共同源码，另一份 Ariane/Nangate45 只有 TNS restoration。A38 的寿命修复尚未被这些未来任务模板消费。
2. `native.run_goal` 重建容器 read roots 时没有保留 campaign 中显式声明的 `build_seed_root`；固定源码 replay 还将 donor 强制覆盖成 `source_seed`。当专业源码是无 build 的私有快照时，会丢掉原构建缓存及其绝对依赖路径。
3. `continuation.run` 重建 read roots 时也会丢掉该显式 donor，续作可能遇到相同问题。

## 改动文件及影响面

| 文件 | 职责/本次变化 |
|---|---|
| `chip_evolve/native.py` | 提前读取原 campaign 已有 donor 声明，将其作为只读 mount 保留；fixed replay 保留原显式 donor；无声明仍使用原 source_seed |
| `chip_evolve/continuation.py` | 原 Goal 续作容器追加其原 campaign donor，只读且不改变原契约 |
| `admin/test_goal_pdk_binding.py` | 覆盖两 PDK、正常演化/固定源码、显式/默认 donor，以及续作挂载 |

这两个业务入口是共享接点，实施前已说明影响面。平台仍只做绑定与确定性执行；构建差量、原专业推理/搜索/晋升属于 Goal。没有跨源码 PYTHONPATH、新服务、API、数据库或对冻结历史的热更新。

未来八组配置单独写在 `var/business/a39-goal-seed-binding-20261025/configs/`，对应 templates 选择已通过 A38 构建/实际故障复测的源码，显式使用原共同构建 donor。原目标、权重、recipe、动作与线程/内存均逐项保持。八组使用各自新 state_root；旧配置字节保持，不能据此宣称旧结果已经消费新修复。

## 短验证和 code-check

- 修改前，显式 donor 的四种新任务组合均复现挂载缺失；修复后正常/固定/续作及原目标/交付等 **48 项针对性检查通过**。
- 根业务 **666 项回归通过**。Ruff、格式检查及使用实际安装依赖解释器的 Pyright 均通过。第一次直接使用 Query 环境做 continuation 类型检查缺少其 Toolkits 依赖；没有改产品去消除该环境诊断。
- 八份实际新模板均由 Goal 自己的解释器/配置解析器加载；新 source、donor 及原目标/权重一致，未调用模型/构建/优化。
- EF `run-ec75aa69302b4d6ea2113989389886ed` 完成一次真实 GCD/Nangate45 原生输入准备；诊断有意停在 native controller 启动之前，不算一次专业演化。
- EF `run-0feaf877b3c046bf9ce5bcc2bdd74600` 通过原 Goal `container_command` 生成的命令，真实读取修复后两份 measured 文件、TNS 文件和 donor FMT 依赖；公开产物日志的四个 SHA 全部与宿主原件一致。
- 本次准备读取已登记的历史 GCD 输入并先通过 DF/DI 核对 scope，没有在新 500 ps 条件下运行基线/优化。已有测量时钟不被新未来配置追溯改写。
- 26 个用户保护文件 SHA 保持；逐文件差异检查通过。

来源与门禁在同目录 `prepared-bindings.json`、`dispatch-verified.json`、`code-check.json`、`test-before.log`、`test-targeted-final.log`、`root-regression.log`、`ruff-final.log`、`format-final.log`、`pyright-runtime.log`。`continuation-before.log` 中测试因启动较晚已经读取修复，不作为修复前失败证据；修改前四例复现以 `test-before.log` 为准。

## 接续

要改变后续的专业源码起点或缓存来源，只修改下一次私有 profile 的 `source_seed` 和原 campaign 的 `build_seed_root`；接入层负责保留二者，不能用缓存二进制冒充新专业源码。实际新构建仍须有自己的 source/binary receipt。

本轮绑定修复完成，长搜索仍暂停。续作交付仍有一处 `previous/inputs/asap7` 写死路径，是下一项已定位的跨 PDK 阻断；不能把本次 mount 资格写成全部续作/八组 PPA 已通过。其余原缺口包括 GCD/Nangate45 500 ps 完整基线与协作、Ibex/Nangate45 完整证明和八组双次结果。优先继续修具体阻断，再做对应短验证。

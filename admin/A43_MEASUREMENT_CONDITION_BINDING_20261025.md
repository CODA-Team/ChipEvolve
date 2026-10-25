# A43：实际测量条件与冻结目标一致

基线根 `926fd66`。本轮仍是具体诊断、定点修复、短验证、code-check；没有启动新 EDA、模型、PDR 或长搜索，没有改服务、容量、公共 SDK/API 或数据库。

## 为什么优先处理

核查辅助固定方法重放入口时，发现共同测量只验证目标中的库文件没变化、实际 SDC 与目标相同，以及本次所选库自身的 SHA 正确；**没有比较本次选择的库集合、corner、时钟元数据、共同工具链与目标声明一致**。因此另选一组有效库或工况时，旧代码仍可能在输出中附上原目标的 condition_id。这是比较事实身份的问题，不能用 Codex 之后的判断弥补。

修改前四种条件变更和四专业派发共8例失败已复现，两份条件匹配用例通过。这里使用单元测量边界证明错误标签可达，不将测试数值当实验数据；没有据此宣称历史采用结果被污染。

## 具体改动与文件职责

| 文件 | 本次职责 |
|---|---|
| `chip_evolve/physical.py` | 内部 `verify_measurement_conditions` 对照实际文件内容和已声明条件；显式目标的 baseline、qualify、measure 均在工具调用前使用；无目标的新基线保持原路径 |
| `chip_evolve/professional.py` | 四专业正式派发在 Query/模型/EDA 前核对目标和本次部署条件 |
| `admin/test_measurement_condition_binding.py` | 不同库/工况/时钟元数据/工具链拒绝；相同库搬目录接受；四专业、完整基线和物理交付均提前停止 |
| `admin/test_query_objective_handoff.py` | 为既有共享夹具补齐与目标一致的实际 SDC/库绑定 |
| `admin/test_invited_paper_relay.py` | 路由交付夹具提供对应 SDC 文件及冻结目标条件，保留原路由行为测试 |

两处生产文件是共享接点，实施前已说明影响面。检查只处理测量条件；不更改 PPA 约束、目标/评分、原算法、候选接受与拒绝、资源或探索性中间态政策。相同内容换机器目录可接受；不同库集合或工况必须有自己的基线/目标，不能套旧条件。旧最小契约未声明的可选工况字段不被擅自补成新要求；当前实际冻结目标均有完整声明。

已存在目标时，所选库内容检查移入同一内部函数，measure 中不重复做一份；无目标时继续原有库 SHA 检查。内部函数不属于外部 CLI/SDK 或 EF/DF/DI 公共协议。原测量 Tcl、freeze_goal、annotate、publish 的 AST 对比全部不变，未增加评分器或评测底座。

## 真实短验证与门禁

八组 A39 新配置逐一对照 A34 已登记历史结果及其冻结文件：七组实际条件匹配；GCD/Nangate45 的新500ps SDC 对旧250ps目标明确拒绝。旧250ps参考本身用其原条件单独核查通过，**没有把未来配置降回250ps或把旧结果改写成500ps**。本轮八组代表中库集合、corner 和工具链声明匹配，不将其扩大为所有历史候选审计结论。

真实 GCD/ASAP7 库集合在私有配置中移除一份后，调用实际 `measure` 入口，明确拒绝，测量目录未创建、EF提交0；原库文件复制至另一位置且内容同SHA则通过。所有原件、26个用户保护文件保持，未改变生产配置或登记新测量。

最终 **59 项针对性检查、682 项根业务回归通过**；五份修改源码的 Ruff、格式、Pyright、逐文件差异检查和模块边界检查通过。第一次根回归的15个失败来自旧测试夹具以空目标/无SDC配置并mock测量：本轮补齐其一致输入，没有绕过生产检查或放宽条件，原失败日志保留。Flow模块未再修改，复用A42的99项通过。

证据在 `var/business/a43-measurement-condition-binding-20261025/`：`test-before.log`、`targeted-final.log`、`root-first-regression.log`、`root-regression.log`、`actual-condition-check.json`、`code-check.json`、`ruff.log`、`format.log`、`pyright-final.log`。私有诊断只读取原文件和复制一份同值库，不做工具运行或新的PPA结论。

## 接续

若要改“是否属于同一测量条件”，改上述内部条件核对；若要改变业务目标，另建正确基线/目标，不能修改旧记录。数据仍为冻结目标/实际部署→EF实际执行→共同测量→DF/DI/Query事实→Codex判断。

辅助 `comparisons.replay_goal` 的固定ASAP7路径仍待下一切片，已定位并未丢弃。GCD/Nangate45 500ps完整基线/协作、Ibex/Nangate45完整证明、八组双次PPA等原业务缺口尚未完成。长搜索保持暂停，不把本次条件核查称作正式实验验收。

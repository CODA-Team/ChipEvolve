# A25准备：完整原生工具操作与GCD时钟单位交接

正式协议仍未冻结。本文是开跑前的操作/来源资格检查，不是A26 PPA或A27端到端效率结果。

## 发现的问题及最小修正

真实原生Codex使用同账号权限、固定镜像与完整原生ORFS执行GCD，综合、布局、CTS、详细布线、寄生提取及finish全部完成，退出0。独立核对全部返回产物hash和固定输入通过，但业务时钟检查失败：原输入含`set_cmd_units -time ns`和周期`0.3100`；原生中间`write_sdc`输出省略单位声明，后续ASAP7进程按ps读成`0.3100ps`。完整工具运行与符合原时钟条件必须分开验收。

修正复用平台**现有通用共同测量入口**已经生成的显式ps序列化SDC：`reference-r3/common/final.sdc`，周期310ps、原IO约束随同序列化。它不是GCD网名/数值补丁，也不修改RTL、库、专业算法或ORFS源码。新部署`local-r6-canonical-gcd.json`仅将GCD原生输入绑定到该既有规范输出；旧配置、旧约束、旧结果和活跃JPEG r4保持。AES/JPEG现有输入已经显式ps，此次没有证明它们存在同一单位问题。

该新部署仍是准备配置。GCD来源复制、环境与目标必须按新SDC字节重新冻结；不能拿它直接套用旧GCD环境、旧目标ID或未经本轮功能验证的历史候选。

## 实际复验

| 检查 | 真实结果 |
|---|---|
| 原生Codex直接操作完整ORFS，使用规范ps输入 | 完整流程退出0；生成时钟两个周期均310ps，全部产物与输入hash核对通过 |
| 同规范输入通过EF执行完整ORFS | EF `run-60d79083987d4bac92e7bfebfa8578f3`成功；两个时钟均310ps；共同FF测量成功 |
| 两次完整原生物理结果 | 原生最终ODB逐字节相同；SPEF仅`*DATE`行不同，其他所有行相同；不改写两个原件 |
| EF→DF→SDK | 新OpenDB/ORFS/OpenSTA三个snapshot可读；七PPA和design/run身份与共同测量一致 |
| DF→Query host→专业上下文 | 当前Codex通过现有host动作查询、带证据回答并导出；专业加载器接受，1事实/0假设，无新增Query内部模型/EDA分析 |
| 约束语义复核 | 对旧参考ODB/SPEF使用规范SDC重新实际测量，七PPA与旧共同测量逐值相同；因此原最终共同评估事实没有因该新绑定改变 |
| 完整功能复核 | 同新目标和规范约束下，重新测量的原参考与新控制全18输出、整体1分区PDR通过；EF `run-15c4815a682b4bc19bc06533865ec926` |

新控制共同FF/310ps事实：功耗`0.001373553765 W`，单元面积`42.6757 µm²`，core/die为`58.7866 / 78.4819 µm²`，setup slack `0.00934292 ns`，setup/hold TNS均0，电气/布局/原生router DRC为0。

旧ORFS参考最终共同评估为`0.0021850110497 W / 56.4829 µm²`。旧参考最终指标仍是原设计在原最终约束下的测量事实，但其原生流程曾承受错误的中间时钟；**正式ORFS对照必须使用新规范输入和新结果，不沿用旧改善百分比。** 该改正本身不是专业协同优化收益。本文没有把新控制自动采用为所有旧目标下的winner。

## 证据与成本

均位于`var/business/a25-formal-preparation-20261017/`：

- 原单位失败：`native-full-design-direct/independent-acceptance.json`，一次原生调用192.70秒、720998输入/7196输出token。
- 规范输入原生操作：`native-full-design-canonical-direct/independent-acceptance.json`，一次157.36秒、739722输入/6913输出token。
- EF控制与数据：`canonical-gcd-unit-control-runtime/experiments/gcd/a25-canonical-ps-native-control-r1/{acceptance,data-acceptance}.json`。
- 约束/功能：同runtime下`a25-canonical-ps-functional-control-r1/acceptance.json`，含旧参考重新测量和新完整证明引用。
- Query：`canonical-gcd-query-host/receipt.json`与`professional-context.json`。

两次原生Codex为同版本`0.159.3`、请求`gpt-6.1-sol/medium`、独立会话及同账号`danger-full-access`，没有sudo、全局配置或服务变动。两次用量、失败与准备全部计入；缓存输入属于输入子集。EF控制由当前线程确定性启动，不冒充“平台侧原生Codex完整操作”试次，也不能用这里的耗时相除声称平台提速。

规范输入调用的首次后验脚本把返回的相对路径按根cwd解析而失败；随后按记录的原生workspace只读解析并核对，通过，没有再次调用模型或EDA，原答案保持。这个后处理错误与原生执行失败分列。

## 对正式实验的影响

下一步先保留正在健康运行的JPEG完整搜索，完成两个Code健康轮次、接力及成本校准；GCD准备使用规范SDC的新来源控制/环境。A25按各设计固定验证模式和真实时钟/IO语义，再冻结公平总预算及精确任务集。A27仍需两个实际原生Codex完成相同冻结任务，包含专业接力及中断/恢复；下面的资格调用工作量不同，不能代替正式对照。

## 本机原生流程资源绑定

`chip_evolve/physical.py`的既有ORFS入口增加私有部署项`designs.<id>.orfs_execution.memory_gib`，交给原EF预约；未声明仍24GiB，原八线程、参数、输入字节、任务身份、物理算法和公共签名保持。配置进入既有设计环境绑定，不以真实占用代替预约批准，也不改变服务总容量。

`admin/test_orfs_resource_binding.py`覆盖旧默认、4GiB和12GiB，检查完整原输入/旋钮与八线程保持；两个显式配置修复前失败、修复后通过。26项相关检查、423项根回归及产品/新增文件Ruff、格式、Pyright通过。此次只给实测完整GCD配置4GiB；JPEG、两个Code构建及其他实验保持自身预约，不能把这个值用于大构建。

原生Codex平台侧完整操作已通过独立验收。通过现有业务CLI启动完整ORFS、监控、完成三类快照导入、读取七PPA，再执行标准`validate`的全部18输出PDR及独立完整物理重放，七PPA逐值相同；最后现有Query host返回带五条证据引用的答案。当前线程独立核对其输入hash、产品源码hash、原生回答、实际EF成功状态、数据身份/七PPA、证明资格与不同物理run的精确重放，均通过。

- 初始物理：`run-8cdd4015ea4d411ab89e15a2b871592d`；共同事实：`run-f994cc3123a54a9cb38133498a5673d3`。
- 功能证明：`run-74001e9a5c284d6787ac2d8976b26e79`。
- 独立物理：`run-bb0a5fc97fd743c3bdcdd1006f84ab3e`；重放共同事实：`run-2793eb7d7fae4bdf94c99c643eb327a9`。
- 独立接受：`native-full-design-platform/independent-acceptance.json`；原始事件、命令和用量在同目录，规范任务在`native-full-design-platform-preparation/`。

这一次实际原生调用405.71秒、1635437输入/7046输出token，1547008缓存输入为输入子集；直接侧仅执行一次完整原生流程，工作量不同，不作效率比值。它没有专业优化/接力、取消/恢复或采用决定。源码身份在启动后另行观察并核对，未假称它属于此前启动清单；正式实验仍须预先完整固定源码及精确同任务。

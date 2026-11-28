# A24：采用入口与现有结果的合格证明关联

这是正式实验前的验收修复检查点。JPEG完整原生Flow仍在运行；A24专业健康轮次与接力、A25冻结及A26–A28业务结果尚未完成。

## 问题与修复

新EQY证明已拒绝在真实时序负例上误通过的旧SAT路线，但`selection.checked_validation`此前仅检查输出覆盖、输入hash、硬约束与精确物理重放。现场只读核查与修复前测试确认：即使旧EQY回执缺少策略或声明SAT，仍可用于一次新的采用。

`chip_evolve/selection.py`现在对EQY回执复用现有`qualified_strategy`检查：缺失策略、旧SAT及未知策略不能授权新的采用；合格`abc-pdr`仍可采用。函数签名、公共数据契约、原Yosys路线、历史读取与原文件保持。没有给历史SAT记录补写PDR字段，没有重造评测服务或改变PPA目标。

`admin/test_adoption_eqy_strategy.py`包含三类不合格策略的实际采用入口拒绝与合格入口接受，并检查旧回执字节不变。三个负例修复前失败，修复后通过；相关43项与根420项回归通过，修改文件Ruff/格式/Pyright通过。

## GCD和AES实际交付

以新的验证文件关联以下既有结果，先核对新完整PDR成功、所有输入hash、原物理复测差值与当前SDK事实，再通过现有`select`入口在A24部署记录采用。旧部署的指针、决定与验证原件保持，不改写历史。

| 设计 | 新完整证明 | 原结果与物理证据 |
|---|---|---|
| GCD | EF `run-957bdb20bc4f4604a841a89a91ed41b4`，全18输出、整体1分区PDR | 保留A21功耗分支；原独立物理重放、七PPA及SDK相同 |
| AES | EF `run-e6c149ab8a154fe9a8318273a1d1042a`，全129输出、695分区PDR | 保留A9 Goal分支；原独立物理重放、七PPA及SDK相同 |

权威关联收据：`var/business/a24-jpeg-pilot-20261016/requalified-incumbent-associations.json`。每设计新验证位于该目录`runtime/experiments/<design>/a24-qualified-adoption-association-r1/validation.json`，带原验证、新证明和原物理重放的明确引用及hash。SDK重新核对参考、候选和原重放三方；没有新增物理EDA任务，没有新增优化收益。

真实旧AES验证已在修复后的只读入口被拒绝；新的两份关联验证通过。GCD原Yosys验证不被推断具有EQY/SAT的相同缺陷，新的PDR是交叉复核。

## 完整搜索与下一步配置

同一JPEG Flow实验`a24-jpeg-flow-r4`、原生campaign `20261016_225329_199041_seed42`继续原2轮×50候选、完整参数域/评分和72000秒预算。初始两个失败候选18/30均为详细布局合法性失败；失败证据已从公开EF按hash保存。候选18实际峰值约1.06GiB、10进程，远低于12GiB/2048上限，候选30也未达限。原worker会保留失败状态并继续其他候选；不删除样本、关闭检查或改动活跃副本。当前证据不足以把失败唯一归因到padding、DPO或新版实现，需要依据后续搜索分布判断。

DPLEvolve下一次运行新建`local-r5-code-pinned.json`，显式固定Teacher/Student为`gpt-6.1-sol/xhigh`，并启用已核验PDR验证配置。新环境实测探针EF `run-48cf7b0b940948498be55ecde62e8d93`成功；环境ID `e8ef3e0781213313b76c7e34a682a0654874cc11ac0fa16e9053a16ceecefe8e`。专业算法、共同工具链和原目标保持，活跃Flow r4配置字节不变。该探针不是Code健康演化轮次。

新原生Codex完整GCD工具路径检查完成：完整原生流程返回0、产物hash核对通过，但暴露原ns输入在ORFS中间序列化后丢失单位，后续将0.31读为ps。工具执行资格与业务时钟资格分别判定，后者失败。正在用平台既有通用测量入口输出的显式ps约束做独立完整复验；原输入、旧结果与旧调用不改写，不作为A27正式数据。正式协议仍须等待完整专业预算校准，不能从版本命令或本文检查推导全流程效率收益。

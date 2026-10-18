# A25：Flow超时证据与阶段资源候选

本轮修复两个影响正式实验准备的接点：外层超时后仍能交付已完成的Flow分支，以及按物理阶段显式配置内存预约。候选已提交、推送并通过工程检查，尚未替换活动队列的版本。正式实验仍未就绪。

## 业务问题和改动

JPEG r4已经在原72000秒预算截止，外层状态为TimeoutExpired、清理完成，但原生摘要停留running。旧证据入口只接受原生明确failed/nonzero，因此无法交付这94份成功物理分支。新入口核对原生campaign身份、已退出owner和匹配的超时/清理回执，将交付侧状态标为timed_out，并引用三份原件的SHA；不改原摘要、期限、完成轮次或失败结论。输出仍为completed-evidence，明确native_search_completed=false。

另一个实际问题是资源预约：已有终态采样中，place最大约1.30GB、CTS约1.05GB，route约9.23GB，三者却都预约12GiB。后续可显式设置place/CTS为8GiB、route继续12GiB。新配置只传递各阶段的EF内存预约，线程、进程额度、算法、完整参数域、模型、候选数、阶段/整场期限均保持；未配置的阶段沿用原全局值，已有部署的默认行为不变。8GiB/12GiB是待实际资格验证的配置，不是已取得的运行提速，也不是所有设计的固定限额。

## 文件、数据流与边界

| 候选 | 文件与职责 | 数据流 |
|---|---|---|
| 超时证据 | 根chip_evolve/flow_evidence.py及admin/test_design_fact_materialization.py：核对终态来源并覆盖真实超时形状 | 原summary/status/cleanup→身份和原件校验→既有候选交付器→EF测量/DF；本轮只验证到交付器入口 |
| 阶段资源 | 根chip_evolve/professional.py及admin/test_flow_execution_budget.py：验证私有stage_memory_gib并传入settings | 部署配置→platform.json.stage_resources |
| 阶段资源 | Flow flow/platform_leaf.py及flow/test/test_platform_leaf_resources.py：选择本阶段预约 | settings→原PlatformExecution→公开EF TaskSpec；原任务身份和恢复校验保留 |

这些是共享运行接点，影响后续Flow启动、叶任务预约和失败后交付。没有改EF/DF/DI接口、数据库、专业选择规则或原生模式，没有增加服务。既有campaign指纹已包含完整settings，既有PlatformExecution也已拒绝恢复时改变资源。

## 验证结果与实际限制

- 超时修复：现场形状用例修复前失败、修复后通过；相关49项、完整根482项回归通过，变更生产文件Pyright零错误/警告。真实JPEG原件经新入口接受且字节保持，但交付器在该检查中被拦截，未完成94分支的实际恢复、复测或DF导入。
- 阶段资源：修复前根7项、模块2项失败；修复后根489项、Flow95项回归通过。生产变更范围两侧各2文件类型检查零错误/警告，Ruff F、相应格式及差异检查通过。测试覆盖阶段选择、未配置回退、原生搜索参数保持和准备前拒绝配置错误；原任务资源漂移拒绝的既有回归保持。
- 首次根回归误包含legacy-integration，模块根目录调用也缺原生相对导入环境；原失败日志保留，未改测试或生产代码迎合环境。按根admin/test_*.py及Flow原flow工作目录的完整配置范围取得上述通过结果。
- 当前26份用户保护文件、r7的68份固定输入全部逐SHA保持。没有新增EDA或模型调用，没有更新活动服务。

## 提交、发布与启用

超时候选为根f72f1e21；阶段资源根候选2d6fbb5在其上追加，分支a25-flow-stage-resources-20261018。Flow阶段资源候选7b1003b在来源校验34d14e8上追加，发布到ChipEvolve的modules/flow-agent-a25-stage-resources。

发布过程中误用Flow origin，新建候选分支推到上游；核实远程仅为本轮7b1003b后，以该精确引用为条件撤回，并核实上游该引用已不存在、ChipEvolve正确引用存在。上游既有分支没有变动。以后此模块发布使用platform remote。

主根仍为730cf0c的业务代码、主Flow仍199bcf1，r7继续原DPL→Goal→GCD完整域校准。当前DPL三条原生基线及第一份源码构建成功，第二份构建正在单LTO链接，后续物理任务等待预约释放；Teacher/Student原生轮次尚未完成。两Code使用原已证明JPEG来源，不是Flow候选接力。

待r7释放绑定后，再启用这些候选、更新gitlink/SOURCE_MANIFEST、重新核验环境并进行真实超时证据交付与资源资格验证。旧运行不注入新源码，不修改旧指纹，不将新规则补记为已生效。完整Flow收尾、真正专业接力、候选PDR/独立重放和预算校准仍是A25冻结的前置工作。

验收记录分别在var/business/a25-flow-timeout-evidence-20261018/acceptance.json和var/business/a25-flow-stage-resources-20261018/acceptance.json；现场续接点继续使用var/business/a24-jpeg-pilot-20261016/continuation-checkpoint-20261017.json。

# A8：正式本机运行、恢复与验证入口

状态：工程验收通过，老板业务验收独立；A9 AES 迁移验证接续进行。基线 3c05323；实际配置 var/business/a8-a9-workflow-20261015/runtime/local.json，继续使用已资格验证的 EF/DF 服务与安装环境，不升级底座或专业算法。

## 业务交付

根 CLI 新增 resume、continue-goal、validate、compare；原 run/diagnose/status/show/select 保持。原 Goal 续作与 placement 交接从 admin 移至正式模块，旧脚本兼容转发。Codex 决定调用和采用，无新通用推理循环、评分或服务。

resume 重接原 EF 身份，或从已完成专业的交付检查点补完物理/测量/入库；不重跑尚未完成的模型搜索。输入内容 hash、命令和任务身份固定，失败记录保留；本机业务锁防止活跃驱动被同时恢复。布局归档复用已冻结包，避免 ZIP 时间戳改变输入。嵌套验证的同名子任务使用不同身份。

validate 通过原 EF：证明所有顶层功能输出，独立目录恢复原专业 checkpoint 并完整 DRT/RCX，核对七项 PPA 和三个 SDK scope/源指标。原始 WS 与衍生 WNS 区分，core/die 原始指标通过 include_raw 读取；默认 canonical 列表不等于全部事实。初次准备时的投影使用错误已修复，日志保留，并增加对应回归。ORFS 可从 RTL 完整重放，DPL 可从布局继续 CTS/route，Goal/ECO 可从专业输出继续。旧比较 CLI 兼容保留。

## 实际证据

| 验证 | 结果 |
|---|---|
| GCD A7 结果经正式 validate | 全部18个顶层输出证明；独立DRT/RCX后七项PPA完全相同，约束干净，DF/SDK身份和源指标一致 |
| 真实终止 ORFS 业务驱动 | 原ORFS成功、common已提交时SIGTERM驱动；resume接回同一run-bed6a7b6aa64448098dad6f508bf33e3，不重跑ORFS |
| 真实终止 Goal 业务驱动 | 原生baseline正常完成、已保存delivery checkpoint后终止；resume补完共同测量/DF，保留native-baseline原判定 |
| 同一validate再次调用 | 原8个EF任务集合不变，新增运行0个 |
| 正式select | 新runtime先保留A7 incumbent，再采用同值独立重放结果；旧结果及采用记录不改写，无新增优化收益声明 |
| 工程门禁 | 根184测试通过；Ruff/format/pyright与差异/边界检查通过；26份用户文件保持 |

证据目录 var/business/a8-a9-workflow-20261015：a8-acceptance.json、interruption.json、goal-interruption.json、validation-reentry.json、a8-adoption.json，各实验的task/submission/execution、delivery-checkpoint、validation、模型证据及proof.log。r2之前的首次验证与失败准备日志保持，不混作最终回执。

## 文件职责与边界

- chip-evolve.py / cli.py：本机HTTP绕过代理、正式命令、状态入口。
- config.py：原部署契约不变，新增单实验本机驱动锁。
- jobs.py：原EF任务身份重接、内容校验、嵌套任务隔离；不改EF接口。
- delivery.py：成功专业交付检查点与确定性恢复。
- physical.py：原测量/布线可重接，ORFS重放可沿用冻结objective。
- professional.py / native.py：原专业成功后保存检查点，恢复不再启动Teacher/Student。
- continuation.py / handoff.py：迁入原已验收续作/阶段交接；两个admin原入口兼容。
- logic.py / validation.py：原EF工具下的输出证明、独立重放和SDK事实检查。
- admin/test_local_workflow.py：中断恢复、活跃锁、内容变化、子任务身份、WS/WNS和物理单元排除边界。
- README、PROJECT、ARCHITECTURE、TASKS与本轮计划/报告：接口、范围、状态和技术债。

修改行为应定位相应正式模块；专业算法继续在原项目，不在组合层重写。

## 保留限制

输出证明固定Liberty，只在EF解析JSON确认没有端口连接时排除物理填充类单元和scope元数据；内部名隐藏，顶层接口、顺序归纳和断言保留。实际网表/ODB不改，数字证明不替代物理检查。验证不会自动采用。

恢复尚未结束的模型搜索继续由原项目能力决定；本片不新造通用会话恢复。重复专业源码构建的成本优化、ECO路径范围和公平性能对照仍未纳入本片。A9需在真实AES上验证迁移，不把GCD通过写成全设计支持。

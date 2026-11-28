# A25：共同物理交付的资源声明传递与真实GCD对照

本轮从真实排队继续核查资源预约，发现并修复一个配置传递缺口。修复在隔离候选分支，真实4GiB对照已由公开EF接受但仍排队；没有启用主版本或取得新PPA收益。A25未冻结，A26–A28未完成。

## 排队原因及两个不同层面

当前AES整体证明run-d223b728…实际running，预约32GiB；公开EF查询明确显示其余任务因资源池剩余内存0而排队，并非任务未分发、worker失联或数据库丢任务。原证明129输出覆盖、策略、14400秒及资源声明保持，未因等待重启。

已取消的旧分区证明ef79实际全进程树峰值5742501888字节，约5.348GiB；当前ABC与两个Python进程的实时RSS较小，但这不是当前完整任务的峰值，也不包括已退出的预处理进程。因此只支持在取得本次完整峰值后校准后续预约，不能直接宣布当前32GiB不必要或16GiB已经合格。现有validation.equivalence_memory_gib即可表达未来配置，不需新API或服务；未扩全局容量、修改正在运行的配额或更换证明。

另有独立、已复现的传递缺口：完整ORFS及来源复制已读取designs.<id>.orfs_execution.memory_gib，但共同物理qualify调用Jobs.command时不传该值，回退24GiB。之前GCD完整ORFS采用过4GiB配置，不等于所有GCD任务都已使用该配置。当前私有canonical-r2复测配置本身没有声明该字段，其24GiB不能归因于EF吞掉一个4GiB声明；新控制同时显式声明4GiB并验证共同入口确实传递。

公开原件与观测位于var/business/a25-relay-strategy-feedback-20261020/proof-reservation-versus-observed-memory.json。

## 最小代码修正与门禁

隔离分支a25-common-physical-memory-20261020从已合格组合根09f95a5创建，提交527489f28900bcf9e7811be5655f2ce159adeb37，已推送ChipEvolve。只改两文件：

- chip_evolve/physical.py：共同物理交付传入既有设计内存声明，缺省仍24GiB。公共函数签名、底座契约、八线程、进程预算、物理Tcl、全部目标/指标/筛选规则保持。
- admin/test_orfs_resource_binding.py：覆盖缺省24、显式4及12GiB共同物理请求，同时核查原producer/目标/八线程/布线及提取动作仍保留。

修复前新用例明确复现两项失败、其余六项通过；修复后24项相关检查及全部567项当前根回归通过。Ruff F/I、格式、按实际生产/测试解释器分开执行的Pyright均零错误/警告，差异与模块边界检查通过。

初次完整测试错误递归收集了归档legacy-integration；改按既有当前根admin/test_*.py范围运行后，还遇到隔离工作树缺少专业源码/工具环境。随后复用此前09根已使用的原生CLI源码fixture、同值DPL registry、已安装wheel环境及原已审查的API-only测试admission；没有新增生产授权、源码路径注入或兼容软链接。缺失环境及首次类型检查误用未装pytest的生产client解释器的记录均保留，最终完整测试无排除当前根用例。fixture来源及SHA见regression-fixtures.json。

## 同一输入的真实4GiB控制

var/business/a25-common-physical-memory-20261020/run_gcd_memory_control.py使用新隔离根，通过既有Jobs/EF执行；不启动模型、专业搜索、重新编译或改动原始候选。输入为已合格重建的GCD Student02原生run-5d6d6036…产物，采用原目标的规范SDC、相同库/RC/工具、完整DRT/RCX及现有DF/SDK交付。

配置只新增该设计4GiB声明和独立state_root；原canonical-r2配置/结果不改。公开EF已接受run-2e80bc29e1f74d5db55436bcead8f411，实际请求8CPU/4GiB/2048进程，当前queued。独立核查新旧route.tcl和完整command request，仅实验输出目录不同，其余逐字同原24GiB控制；目标、原生producer及全部固定输入身份通过。

原24GiB run-ebcc8327…继续保留，不因新增控制取消或替换。新主管1990182/start_ticks861542453，102固定输入及26受保护文件已核验。后续必须收取实际终态、峰值、注册原件/七PPA/SDK，并与原候选及24GiB控制比较；尚不能称4GiB已完成实际运行或不影响PPA。若失败，只诊断该同输入控制，不自动升级配额或改算法。

独立门禁及实际提交证据为independent-engineering-and-submission-acceptance.json；specification.json、launch/receipt和runtime下原请求保留。该新任务尚未终态，不提前计CPU或重复计原构建/模型费用；准备/测试和主Codex成本不填零。r65既有账本保持，下一份费用快照需包含该新run及此前pending终态。

## 当前边界与后续

AES仍求解、原完整JPEG2×50、其余策略/选中源码最终复测、原生完整参考和1719378真实接力继续；未改它们的固定代码、配置或资源池。本轮不重绑已固定的JPEG接力，因为其缺省24GiB语义保持。正式冻结前须结合真实峰值和完整运行，把适当的各设计/操作预约明确写入配置，两侧采用相同业务资源规则。

真实控制通过后才考虑安全收口此候选；之后仍须完成精确来源/模型/AST/EPD/停止与冷暖状态冻结，以及A26 PPA、A27同Codex完整业务和A28审计。团队PPA无需与单项同总预算，保留原硬约束并报告全部成本。

主根本轮仅本报告及TASKS.md；产品两文件只在上述隔离候选。受保护admin/evaluation用户代码与DF/DI工作修改未执行、部署、stage或修改，现有EF/DF服务未重启。

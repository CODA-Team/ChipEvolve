# A25：专业初始化事实与共同ECO环境

## 本轮交付

两项源码缺口已在隔离分支修复并发布，当前固定实验没有热切换。A25未冻结，A26–A28未执行，正式实验尚未就绪。

| 缺口 | 最小修复 | 工程验证 |
|---|---|---|
| Goal实测基线丢失模式，误走历史未知基线初始化路径 | 新baseline写timing_only/legacy_setup；只补未知、未晋升seed的事实身份；原同模式重测/时序恢复算法不改 | 8新增检查、3项修复前失败；426检查中423通过/3原条件跳过；涉及文件类型零错警告 |
| ECO默认RC与当前Goal共同RC不同 | 私有professional.eco.pdk_template显式选择共同PDK；保留原默认，准备原生NLDM目录及所选设计库 | 4针对检查、原3项中2项修复前失败；479根回归、类型/格式/Ruff F通过 |

实际M2电阻：原ECO为0.0297126，共同Goal为0.0462311；两者RCX规则同字节。同一OpenROAD版本不能代替脚本/库/RC/约束核查。实际JPEG平台Tcl仅重定位已验证同字节的checker路径后与旧原件逐字节相同，原物理序列、目标、评分和晋升规则保持。

Goal候选378863b发布到modules/goalevolve-a25-baseline-mode，文件：goalevolve/cli.py（事实交接与原内部类型说明）、goalevolve/evaluation/contest2026.py（实测metadata、显式原默认值与类型收窄）、tests/unit/test_measured_baseline_identity.py。历史缺metadata、已知模式、已晋升parent保持；原23项类型诊断经内部注解/cast与等价None收窄消除，没有运行算法变化。

ECO候选8207f64发布到a25-eco-pdk-alignment-20261019，文件：chip_evolve/native.py（3新增行/1替换行）、admin/test_eco_pdk_binding.py（真实输入准备在EDA前截取）。没有EF/DF/SDK公共接口、原专业源码/提示/动作变化。

## 正在执行的队列

原R10的GCD完整2×50继续，当前进入第二轮CTS。旧Goal四份最终完整布线/SDK已核验，但全部setup失败、零采用；Student03自己的对象及Query上下文已通过，不能复用Student01的路径诊断。

原following master依次负责安全启用、JPEG原94完成分支事实恢复、DPL实际资源资格和五个匹配物理控制。94/100超时搜索仍不是健康完整搜索。

新增串行后继PID4075886已启动，状态waiting_existing_serial_pipeline。它要求上述整个队列成功退出，才合入ECO候选、重跑主树回归并发布，然后依次执行：

1. a25-jpeg-goal03-eco-common-pdk-r1：原Student03产物及其Query，原ECO有界8轮/7200秒，共同PDK/FF/545ps及原目标。
2. a25-jpeg-goal-measured-mode-r1：原JPEG来源、目标、Teacher/四Student完整一轮/43200秒，验证模式事实修正后的实际行为。

15项新输入已固定，启动前只读预检通过，尚未派发这两项新专业实验。原R10的78固定输入和26用户文件逐项校验全同。最终通过全部原硬约束才继续现有validate的27输出PDR与独立完整物理重放，采用JPEG实测32GiB/4worker/14400秒证明配置；不自动采用、不降低约束。

## 保留的失败和边界

隔离测试初期的缺资料、错误解释器依赖和本机代理失败均保留；补齐原版本最小资料和已安装公共wheel环境后通过，没有削弱断言。无关的17GB完整发布快照校验因大量读取干扰活动队列而中断，不记通过；发布数据仅作同项目只读硬链接，没有再复制17GB源码。

一次历史Tcl补核误用build_runtime，意外申请版本查询run-6c15b4e3c8374c6c8aa8d513572cdbb4。本次两个诊断进程已停止，该自有排队任务经公开EF取消，终态cancelled；没有优化/模型执行或旧baseline Tcl/结果改写。额外诊断进入失败/成本账本，原30项专业任务不再等于此目录当前全部任务。后续直接构造evaluator的无运行补核通过。

正式冻结前还欠：健康完整JPEG Flow、资源/注册来源实测、上述真实专业接力、全约束/证明/重放/成本核对；然后执行公平PPA、同原生Codex完整操作对照及交付。四份Goal最终失败不能包装为协同收益，Query读取字节不能包装为正式token节省成绩。

证据：var/business/a25-goal-baseline-mode-20261019/、var/business/a25-eco-pdk-alignment-20261019/。后继方案/回执为前者continuation-specification.json和continuation-receipt.json；已固定文件不回写。总续接状态仍为var/business/a25-dpl-operation-resources-20261018/CURRENT.json。

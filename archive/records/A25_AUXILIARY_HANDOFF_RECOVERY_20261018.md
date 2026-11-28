# A25：专业布局交付的辅助脚本路径修复

2026-10-18约21:14，DPL原生Teacher计划、三Student和Teacher review均正常结束，按原规则选择Student02。CTS实际消费正确候选并成功，route_finish在Make展开时引用已不存在的`/work/inputs/fastasap_floorplan.tcl`而失败。原r7及两个衔接器已按既定规则停止，没有重开搜索。

## 根因与修复

ORFS来源已通过`design.flow_dependencies`声明两份真实脚本，`baseline_overrides`引用其容器内路径。根`professional.flow_source`只追加原配置，没有复制和重定位依赖，因而带入了上一任务的临时路径。根提交f9ffaa6复制已声明依赖到新来源的`flow/source-bindings/<destination>`，保持目录关系，并替换对应引用。脚本字节、参数、算法、公共签名和EF/DF接口不变。

修改文件：`chip_evolve/professional.py`承担来源继承；`admin/test_flow_auxiliary_handoff.py`覆盖任意设计名、不同目录中的同名脚本和无依赖的原行为，没有JPEG条件分支。24项针对检查、475项根回归、Pyright零错误/警告、Ruff格式/F及差异检查通过。没有新增服务或通用harness。

## 真实恢复进行中

原成功CTS为`run-411a59ef3010463e8f11eb3f2f7b9987`，一次attempt，实际候选布局SHA为cf499ad5…，没有重跑。失败布线`run-9c6b9e9096b74dabb192e79429e490a0`及原业务失败状态保留。

恢复目录为原runtime下`experiments/jpeg/a25-jpeg-dpl-s02-delivery-r1`。私有校准脚本复用原`resume_layout`、公开EF及数据交付；仅在CTS接点借用原成功任务，核对设计、父run、目标、单次attempt、SDC和归档SHA。新布线采用新命名空间及正确继承的来源，父run仍是原CTS，没有重跑模型搜索或编译。

恢复监督PID1291376；新布线`run-0c8d14099eaa4abb9956062475fb15b8`已由EF接单运行。仍须完成RCX、共同测量、DF/SDK及其余两候选交付和独立验收，不能写成恢复通过、共同PPA改善或采用。恢复脚本首次直接文件启动在EDA前因找不到根包失败；随后改用工作区既有`python -c/runpy`入口，没有新增PYTHONPATH或跨源码安装。

证据在`var/business/a25-dpl-operation-resources-20261018/selected-route-failure-r1/`和`selected-route-recovery-r1/`。固定旧失败、原CTS、布局/源结果/目标、辅助脚本、业务实现和26份用户文件的SHA；不回写原68项队列清单。后续Goal/GCD必须用包含本次修复和恢复验收的新续接清单，保持原命令和失败账本。旧失败衔接器不再是等待中。

A25尚未冻结，A26–A28未开始。

## 21:35：所选分支已完整交付，PPA不合格

新布线一次attempt成功，实际CTS输入归档与原注册CTS逐SHA一致，输出消费日志确认继续读取4_cts.odb，原cf499ad5…布局未被上游重跑覆盖。随后共同测量run-da5fa8ff2b0f49c5bc9355cbc851d47b完成，OpenDB/ORFS/OpenSTA三视图各一次导入成功；公开SDK的设计/run/snapshot及全部数值与实际结果一致。所选分支的路径交接、完整DRT/RCX和EF→DF→SDK恢复已通过，其他两候选仍在交付。

| FF/545ps共同事实 | 本候选 | 原上限/要求 |
|---|---:|---:|
| 总功耗 | 180.38398027mW | ≤178.33724618mW |
| 单元面积 | 6750.60µm² | ≤6734.18µm² |
| setup slack | 0.53868ps | setup TNS≥0，当前为0 |
| hold TNS | 0 | ≥0 |
| 布局/电气/布线DRC | 均0 | 均0 |

父级Codex基于原约束决定不采用当前分支，保留已有合法来源；没有因原生HPWL更优而替换结果。本次证明局部目标与最终目标有冲突，尚不能把退化唯一归因给算法或交接。后续须保留同流程的原布局/框架匹配控制，区分阶段转换、布线策略与Student变化，再选择真正的接力来源。完整功能证明及独立重放未在本次新分支上完成，也没有采用。

独立证据：selected-route-recovery-r1/selected-delivery-acceptance.json、selected-sdk-metrics.json及selected-sdk-stage-summaries.json；业务决定在selected-student02-preliminary-business-decision.json。原失败/CTS/模型搜索保持原字节。

新r8监督PID1370641已等待全部恢复交付，随后自动独立审计，再执行原Goal一轮四Student与GCD完整参数域2×50原命令；绑定73份输入。替代来源启用监督PID1370818等待r8，新资源资格PID1370959等待此前交付。三者均已启动等待，尚未通过；旧三个失败监督不重启。全原生五次调用均正常返回，已知输入加输出87,589,800 token，其中86,076,544为输入内缓存子集；原事件用量完整性限制和数据/恢复费用继续单列。

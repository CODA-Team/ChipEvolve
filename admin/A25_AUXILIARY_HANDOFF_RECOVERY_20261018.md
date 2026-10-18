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

# A25：原生专业入口检查与检查路线收敛

生产 Gateway 的真实下一批 JPEG CTS 已确认50/50槽位接单，原完整搜索继续。额外的原生 Codex 固定专业接力检查没有完成全部验收；三次尝试和成本保留，停止追加这条低层检查路线。A25 未冻结，A26–A28 未启动。

## 已核实的能力与未完成的业务

同一份真实 DPL AES 输入和已构建 Goal Student4 功耗源码，在 r2 中完成原专业动作、完整 DRT/RCX、FF810ps共同测量及DF发布，四项任务各一次attempt成功。最终功耗0.034947216511W、单元面积1254.13µm²、setup slack0.201938ns，setup/hold TNS均0，当前SDK七项数值一致；相对父DPL功耗0.034848373383W，功耗增加，不能作为更优交付。

但 r2 原专业回执缺少父run标签和design_context，所以完整入口资格没有通过。r3改用原生项目内正确模块入口后，实际请求包含DF查询上下文，公开EF的父run为`run-ad77204de2394387a2a9a11f634301dc`，目标ID为`652fbf7464aa374039584693365c637205dfdb59783ea2931f7efe0e73c8bd21`，新原生run为`run-9e974f867f0e43dea26adb9e51519af5`。其原始二进制哈希保持，四份关键原生网表/数据库与r2逐字节一致。该部分通过独立核查，只证明专业动作、数据入口及输入身份，没有把r2最终物理结果拼接成r3的新结果。

## 三次尝试的真实结果

| 尝试 | 现场结果 | 原因与处理 |
|---|---|---|
| r1 | 首次原生EDA因无法写产物失败；一次attempt，未重跑 | 检查任务允许手动改绑定，模型把同一输出目录同时绑定RO/RW；准备器随后固定互不冲突的目录 |
| r2 | 原动作/完整布线/测量/DF与SDK成功；缺原专业输入上下文，完整资格失败 | 从外部绝对脚本入口导入了旧editable安装的`control-r5`模块；已有产品入口使用原项目cwd中的`-m/-c`，无需修改算法或安装包 |
| r3 | 原动作成功，DF上下文及EF父run/目标标签正确；后续布线在提交前被HTTP409拒绝 | 私有`Jobs`组合器在正常业务目录以外采用目录basename，不同会话都叫`workspace`，命名与r2冲突；原不可变任务没有被覆盖，没有新增该布线run |

两个Code的OpenROAD研究二进制及原算法没有在这些检查中改变。错误发生在检查器准备、Python模块选择和私有组合器的调用范围，不能把它们写成EDA算法或最终PPA失败。

## 后续采用的验收入口

这项检查把目录绑定、原模块导入和实验命名等机械配置交给模型，偏离了平台让Agent只关注业务的目标。停止r4低层模型重试，未派发直接侧，也不形成成功配对或效率比。后续完整原生Codex专业操作资格使用既有业务CLI的设计/key目录、原生`-m/-c`启动及统一结果交付；直接侧仍可使用相同原算法和工具，按实际同任务条件冻结。

`Jobs`在正常业务布局以外的basename行为列为私有调用限制。当前业务CLI为设计与key建立独立目录；本次没有修改该类、公共接口或活动搜索代码来迁就检查器。正式运行身份清单须包含实际加载模块的路径和哈希，不能只记Python环境路径或包版本。

JPEG原完整Flow继续，之后r6队列按原顺序执行健康DPL一轮三Student、Goal一轮四Student和恢复完整参数域的GCD两轮各50候选。专业真正接力、候选完整约束/证明/独立重放、完整成本校准和正式协议冻结仍待完成；这里的同字节证明和SDK一致性不替代这些门槛。

## 证据与成本

运行证据均在`var/business/a25-formal-preparation-20261017/`：

- `native-stage-deployment-recovery-r2/post-resume-actual-cts-intake/acceptance.json`：实际新批次50槽位接单，接单与物理成功分别记录。
- `native-platform-professional-handoff-r1/`、`r2/`、`r3/`对应完整名称目录：原生事件、真实调用、结果/失败与用量；原始回执不改写。
- `native-professional-handoff-preparation-r3/native-entry-only-independent-acceptance.json`：公开EF、父run、DF上下文、二进制与四份原生产物同值。
- `native-professional-handoff-preparation-r3/namespace-collision-independent-evidence.json`：两份同名不同内容task及哈希、新布线未派发证据。
- `preparation-costs-r22.json`：包含三次尝试的实际模型用量、CPU与失败，不重复累加缓存输入，也不把根Codex及独立服务未知开销记零。

本次仅有私有运行准备/核查脚本及文档变化，没有修改产品或研究源码。实际服务、专业目标与算法、用户26份保护文件保持。

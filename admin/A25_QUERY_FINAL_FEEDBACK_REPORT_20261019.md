# A25：最终负结果进入现有Query上下文及比较提示修正

本轮继续正式实验前工作。已把真实JPEG最终负结果通过现有Query host、DF/DI及专业上下文接口整理出来，并完成一项很小的提示修正候选。没有新Agent循环、服务、数据接口、判分器或专业算法修改；PPA/效率正式试次仍未开始，A25未冻结。

## 已实际完成的反馈

当前Codex作为现有Query host，在固定的JPEG最终共同测量快照中读取指标、约束及注册原始JSON，再调用现有比较接口、带引用回答并导出code角色专业上下文。没有启动额外内部模型或EDA。对照实际为Student01最终结果；它与无CPP增量配方父项的native ODB同字节关系已经由另一份原件审计证明，本次Query没有重新采集该关联。

| FF/545ps最终测量 | 对照物理状态 | Student03 | 候选减对照 |
|---|---:|---:|---:|
| setup TNS ns | −0.573876 | −0.766489 | −0.192613 |
| setup最差余量ns | −0.0308414 | −0.0330878 | −0.0022464 |
| 总功耗W | 0.15525515378 | 0.15527968109 | +0.00002452731 |
| 单元面积µm² | 6378.88 | 6378.88 | 0 |

四项差值来自实际数据接口返回，不由新评分程序计算。两份注册原始JSON读全后与源SHA核对，完整evaluation_conditions同值：实际加载SDC、15份库哈希、工具链、FF/0.545ns、单位、propagated clock及目标/条件身份一致。每份候选的实际布线/SPEF仍各自独立，不把“相同评估方法”写成两份物理产物相同。

交付位于`var/business/a25-jpeg-final-feedback-query-20261019/`：professional-context.json、完整原始证据页、接口差值、最终公开状态及independent-context-acceptance.json。专业上下文含4条事实、5条限制、15份证据及4份原输入引用；现有已安装Toolkits的公开load_context通过，全部事实引用有效，限制未混入事实。两个ORFS视图没有路径或对象事实，因此本包不虚构CPP动作归因、完整功能证明或最终布局签核。

**这是可供后续Codex检索的历史反馈，不是已被下一个专业Agent消费的闭环。** 新Flow父项必须获取自身绑定的fresh Query上下文，不能拿这个旧候选包替代。下一轮是否实际使用这些负结果、是否改变策略以及最终收益，仍要用真实接力证据核验。

## 发现并修正的调用提示

本轮按现有提示尝试WS/TNS名称比较，两项均返回INCOMPARABLE，理由是观测缺失；使用metrics返回的实际raw_key后，四项比较均COMPARABLE。展示名、存储观测名有差别，原Query提示未讲清楚。比较接口本轮unit为null，单位由原始JSON的ns/W/µm²声明核对；不能只凭COMPARABLE认定物理条件或单位已经校验。

隔离Query候选48b105b仅改两个文件：

- src/query_agent/application/investigation.py：现有运行提示说明ORFS比较需用返回raw_key、核对原单位；同一调查的CLI分页会更新checkpoint，应顺序读取。
- docs/investigation.md：同步这三项使用约定。

没有修改DF/DI公共契约、数据、数学比较、查询路由或模型决策规则。保留其他provider可用SETUP_WNS等实际观测名，不硬编码所有数据都属于ORFS。

本轮并行读取同一调查证据页曾被ConcurrentInvestigationUpdate拒绝；这项保护避免覆盖checkpoint，不当作数据底座损坏。后续沿同一调查顺序读取并保留成功页，没有重建调查或EDA。一度误把所有操作都期待为read的本地核验脚本，已按真实14次read、6次evidence_page及1次合法handoff_export修正；没有重写业务状态。首次三个scope请求也因既有最多两scope契约在创建调查前拒绝，原失败保留，实际调查使用两个ORFS scope。

## 候选验证及费用范围

Query全164项回归通过；全量Ruff通过、178文件格式通过、Pyright零错误/警告、三个依赖契约全部保持。最初新增提示一行过长，已换行修正，不改无关文件。构建wheel的实现字节与最终源码一致，SHA554942fb9ed63917044d487c322dc7b6216f4adc67c37fb2eae4a140ec9fb6ec。实际记录在`var/business/a25-query-metric-guidance-20261019/`。

候选推送ChipEvolve的modules/query-agent-a25-metric-guidance分支；**未合入主Query、未安装到生产环境**。当前所有冻结搜索和后继绑定保持。仅提示/文档调整未增加模仿提示文本的测试；既有完整回归及此次真实原键比较作为验证，不宣称新提示已经通过模型效率对照。

实际Query记录21项操作、203377读取字节、0次分析；application_active_seconds约4.20秒仅为被记录的应用活动时间，不包含本次host Codex推理、命令间隔或端到端墙钟，不能宣传为完整诊断速度。未额外启动内部模型不等于总推理费用为零；主Codex token、DF服务CPU仍未单独观测。错误调用、交付前一次复核和本地核验修正保留；费用观察单独存档，不与原Flow/Goal成本重复累计。

## 当前计算和后续门槛

末次公开观察：完整JPEG Flow首轮50place为24成功、7失败、4运行、15排队；这是首轮中间状态，不是两轮完整搜索完成。原主/Flow/AES/原生参考/真实接力以及两个新校准主管均核对PID/start ticks仍存活。AES完整ORFS run-35011a297b2847e0a3537d6f91eecddd已succeeded，但common测量任务尚排队，结果文件未交付；来源复制、129输出PDR及环境资格还没有通过。

四配方校准首项run-cd7d070387024d81918c00ba3454d6bf和合法化Diamond首项run-b1ab332004364c9caf913d725885c909仍queued。继续观察同一run，不因排队重启。原生完整专业参考与真正Flow→Query→Goal仍等待既有前置，未当作已运行完成。

正式前继续取得这些实际结果、核验最终反馈被真实专业决策消费、收口尚未启用的修复并重新绑定环境，再冻结各方法充分投入/来源/停止规则，实际执行两项正式实验。团队PPA投入无需与单项相同；平台效率仍用同一Codex完成同样业务。26份用户文件保持，受保护评测代码和未部署DF/DI工作没有运行、部署或提交。

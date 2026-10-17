# A25：GCD完整候选交付与默认搜索范围修正

GCD预演已完成原生两轮、每轮50槽位及全部最终数据交付，100份结果的700个数值与公共SDK逐值相同。独立核算原业务约束后，可行结果为0/100；因此本轮没有可采用的新Flow结果。原合法保留分支不受影响。本轮既有九份CTS提交前故障和后续复制仍完整保留，不算健康或公平正式试次。

## 已确认的限制与纠正

默认GCD接入配置继承了10月14日本机试验的窄范围：利用率20–35、全局padding 0–1、详细padding固定0、density addon 0–0.20。共享原生范围分别为20–99、0–3、0–3、0–0.99。初始约束处理会保留首行65% baseline，却把后续合法65%/80%建议截为35%；实际100份最终配置仅两份保留65%，其余23–35，70份恰为35%。此前“完整参数域”的描述不准确，本报告纠正该描述；原实验记录不回写。

约束失败数量可重叠：cell area 76份、core area 98份、die area 98份、setup TNS 42份、power 40份。窄利用率范围对轮廓超限有直接配置证据，但不能据此断言它是所有失败的唯一原因。完整来源自身cell area 44.8918µm²超过正确ORFS控制的42.6757µm²；恢复范围也不能保证搜索必然产生可行结果。

## 改动、验证与边界

- `flow-agent/flow/drp_config.json`移除默认GCD的placement覆盖及与共享值相同的CTS覆盖，继承原共享域；其他设计和配置字段语义逐项相同。
- `flow-agent/flow/test/test_initial_constraints.py`保留显式自定义范围截断测试，新增真实默认配置继承和65%/80%、padding3、density0.75原样通过的测试。新增两项在修复前失败，修复后82项模块回归、Ruff、格式、Pyright、JSON解析及差异检查全部通过。
- 不改原生DRP、模型、评分、CP0功耗、阶段继承、全局PPA约束或公共模块接口；本次没有新的模型搜索或PPA改善结论。
- 模块发布到ChipEvolve的`modules/flow-agent`分支。后续GCD和JPEG分别建立新环境，复用已验证的来源复制证据，通过EF重新查询工具及四专业入口预检；旧配置、环境清单和活动JPEG副本保持。
- 26份用户工作文件哈希全部相同。未部署DF/DI或用户evaluation工作。

## 现场证据与下一步

运行证据位于`var/business/a25-gcd-canonical-source-20261017/`：`full-flow-final-data-acceptance/acceptance.json`及参数分布、`gcd-domain-fix/before-tests.log`、`flow-regression.log`、`gates.json`和`environment-requalification.json`。新GCD配置为`runtime/local-qualified-r2-native-domain.json`，后续JPEG Code使用其原运行目录下`runtime/local-r6-code-pinned.json`。

JPEG原完整2×50 Flow继续，尚未交付完整轮次。生产Gateway仍为旧版本，更新必须等真实消费者与公开EF队列均空闲；之后做实际50客户端/150上传和历史SDK核验，再运行恢复原范围的独立GCD实验、健康Code轮次和接力。A25未冻结，A26–A28未开始，尚无同预算团队PPA或端到端效率优越性证据。工程检查与老板业务验收分开。

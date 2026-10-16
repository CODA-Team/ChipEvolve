# A25准备：实际Codex判断、交接语义与原始开销

本轮仍是A24进行期间的A25准备；协议未冻结，A26/A27未启动。JPEG完整功能证明未得最终结论，不能据本报告宣布完整专业预演、正式收益或全平台验收完成。

## 原生Codex实际完成了什么

一次原生`Codex 0.159.3 / gpt-6.1-sol / medium`调用，用既有Query `--model host`接口自行选择读数、查看原始来源、比较、带引用回答并导出专业上下文，没有第二个Query内部模型或新EDA。独立核对原测量与原先保存的路径事实，得到：

| 问题 | 实际判断与核对 |
|---|---|
| 对照最差的同一路径是否改善 | 相同端点、post_route/setup/FF/秒单位，控制path:10对应候选path:13，裕量改善20.65ps |
| 各run自身的最终最差裕量 | −35.5112ps→−20.1413ps，改善15.3699ps；不能与同一路径差值混算，最差端点发生切换 |
| 是否闭合时序 | 否，候选仍为负裕量，不得采用成合法改善 |
| 原因能证明到哪一步 | 到达时间提前、匹配required time不变，支持报告的数据传播变快；库单元/路径变化是候选机制，现有证据不证明唯一原因 |
| 限制是否保留 | 原始加载SDC/ODB/netlist/SPEF有差异、完整SDC语义未核实、部分RC关系不可用；WS比较曾返回INCOMPARABLE，模型显式披露并独立读取实际原生指标计算 |

证据：`var/business/a25-formal-preparation-20261017/native-query-host/`。`independent-acceptance.json`核对数值、引用、身份、原包加载及全部三个本地调查的零EDA分析；它没有覆盖下面的分类缺陷，不能作为完整交接语义合格证明。

该次调用耗时381.58秒，输入2,082,058、输入内缓存1,850,752、输出14,203 token；43条命令中13条失败，三个调查均保留。早期范围选择、数据投影和动作格式摸索均有开销。没有直接侧配对，不能声称更省成本或判断能力优越。累计准备成本见`preparation-costs-r3.json`，主Codex推理等未知成本仍非零、未计全。

## 两个实测缺陷及修正

1. 现有host入口缺少直接发现动作格式的命令，模型只能从验证错误摸索字段。Query提交`9ab92b8`新增只读`decision-schema`，输出既有`InvestigationDecision.model_json_schema()`，无需调查、服务或模型。原字段及验证规则不改；两项修复前失败、修复后通过的检查和全163项回归保留。
2. `professional_context`把所有最终claim追加到`confirmed_facts`。真实旧包10条中4条精确重复、1条为明确possible假设，另有限制claim。原包仍留在原处，`semantic-acceptance.json`判此语义检查失败。Query提交`7bee5ba`只修新导出：精确去重，假设及possible/unknown声明放入hypotheses，限制带引用放入limitations，保留原输入/引用/范围与原假设。新声明仍须引用已打包证据；不制造新结论或编辑权限。

两个修改分开提交，未改公共EF/DF/SDK签名、专业算法或Query决定数据结构。历史上下文仍可读取，不回写历史分类。安装前原生调用已经终止，无其他Query进程；旧包备份后仅以wheel更新本轮既有Query环境，没有后台重启。

## 实际重导出核对

复制已结束调查的状态，沿更新后的公开CLI导出，不重跑模型或EDA。新包为4条确认事实、1条未确认假设、5条限制，全部32条原证据逐条保留；正常导出又新增一条相同scope的输入来源摘要证据。原状态和原包的全部核对hash不变，现有专业加载器接受新包。

初次核对脚本错误要求新旧证据列表完全相等，因此留下失败回执；随后只读已生成结果确认“原32条均未改变，新增1条正当的来源读取”，没有重导出。权威补核为`native-query-host-reexport/posthoc-acceptance.json`。这证明新包正确组织已有材料，尚不代表某个Code新搜索消费了这个包。

待启动的完整Flow也用了相同旧分类形式。已对同一原来源调查重导出新包，并沿根既有格式保留`identity_bindings`。仅中断尚未启动EDA的旧等待器，归档原记录，替换为使用新包的等待器；同一个`a24-jpeg-flow-r4`、原2×50、完整参数域和72000秒上限保持，原证明与后置检查等待器未停止。记录为`var/business/a24-jpeg-pilot-20261016/flow-context-prelaunch-upgrade.json`，没有重复搜索或修改旧输入。

## 文件职责、验证与边界

| 文件 | 本次职责 |
|---|---|
| Query `interfaces/cli.py`、新`test_host_decision_schema.py`、`docs/investigation.md` | 发现原动作契约及无服务/模型副作用核对 |
| Query `application/professional.py`、`test_professional_context.py` | 分类、去重、引用保持、原状态不变和确定性身份；限制不误作确认事实 |
| 根`admin/run_native_codex_episode.py`及测试 | CLI仅打印紧凑回执位置/状态/用量，完整命令原文留在事件与收据中，避免再次把巨量日志倒入调用者上下文 |
| 根架构、任务和manifest、本报告 | 固定Query的两个发布提交和剩余验收边界 |

最终Query全164项、根全413项回归通过；产品及本次文件的Ruff/格式/Pyright通过，Query三条依赖契约保持。既有扩展旧测试风格问题仍按上一报告保留，不把它写成全历史lint通过。26份用户文件保持原hash。Query wheel SHA为`1724716a9cfe6bca00f5f7720e03dbe9df84eea3cf6adaa5f4ea72012bfb47ed`。

两Code下一轮构建前的源码/种子核查另记录`code-link-policy-observation.json`：实际两份seed的link.txt都有`-flto=auto`及显式`-flto=1`，现有适配会保留单LTO worker，32GiB构建预约能放入当前32GiB池。它只是实际文件核查，没有新构建或健康原生轮次声明。

继续顺序：JPEG全证明→单次完整Flow→GCD/AES独立PDR和参考STA补充→适用Code健康轮次与证据驱动接力→A24预算校准→A25冻结→A26/A27公平完整对照→A28交付。Query正确解释旧数据、接口检查或保留最好分支，都不能代替最终PPA与完整操作效率的正式证据。

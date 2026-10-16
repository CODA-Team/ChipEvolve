# A24：失败证据、实时进度与完成候选交付

最新：EF/Toolkit已完成安全原位更新，真实派发/取消/失败托管、GCD七PPA同值和历史AES查询通过；JPEG接力已完成但时序仍不合格，未采用。当前环境、实际账号OOM与后续完整验证见[A24运行验收](A24_RUNTIME_ACCEPTANCE_20261017.md)。下文保留本片各检查点的实际进展，不把准备状态当最终验收。

本片仍属已批准的JPEG预演和正式验收准备。完整A24、A25冻结及A26/A27两个正式实验尚未完成。运行证据在`var/business/a24-jpeg-pilot-20261016/`，历史失败不改写，26份用户工作按原hash保护。

## 已核验的业务交付

- 旧JPEG两轮50候选Flow原生exit1、完成轮次0保持。15个实际完成物理分支已全部共同测量、DF入库及SDK身份/七PPA核对；四个满足全部原约束。最低合法功耗178.09300125mW，canonical为178.33724618mW。这是失败批次中的完成分支事实，不是完整搜索成功，也未自动采用。
- 分支45功耗172.81705141mW，单元/轮廓/电气/布局/DRC通过，setup TNS违反原限值。共同最差slack约−15.7994ps，SDK跨路径组排序查到实际reg2reg路径。Query正在准备本候选对象及新上下文，以决定是否做时序恢复接力；未放宽约束或复用baseline上下文。
- 历史AES三个完成DPL候选已完整CTS/DRT/RCX共同交付和SDK核验，温态再次交付新增EDA为0；原HPWL晋升拒绝保持。这验证全部完成候选可被观察，不等于新Code搜索成功或正式效率收益。
- 两个已超时的Goal物理实验原始日志、Tcl及部分阶段指标已从其后续成功解析任务的注册ZIP恢复。公开EF原输入hash、原leaf输出、解析器实际输入、ZIP成员hash逐项一致，经现有analysis入口补充登记给canonical设计；Query能按作用域读到两个引用。原failed、143退出和7200秒超时保持；没有生成失败设计的FinalFrame或新EDA。

恢复证据分别指向failed run `run-29e5d619f47e4c78ad4b8094dab21fa5`、`run-bc13d80d52764cc09e03f01d4260a3d5`，补充analysis为`run-6e380a8c7b164d809d958487a067940e`、`run-f708a23aa6b943c68a75bd0fc04dd909`。日志显示原`repair_power -phase early_forced_reclaim -proportion 80`进行了大量实际单元尝试后达到期限；不能据此断言EF未消费任务、版本错误或唯一算法根因。

## 本片最小修复及边界

Toolkit `688174b`在native命令普通非零退出时登记其真实输出目录和显式额外产物，标记`incomplete_output`，保持原失败和退出码，不发布`data_snapshot`。三个针对回归含真实Runtime托管读取失败日志，完整66项、静态/类型及改动范围格式通过。新wheel与已提交源码逐字节一致，尚未部署到生产；guardian硬杀仍不能保证收尾文件全部形成。

Goal只改`goalevolve/platform/execution.py`：原Popen仍写原stdout/stderr文件，新增轻量转发线程进入EF实时extractor日志；原命令、文件字节、超时/终止及返回规则保持。`tests/unit/test_platform_live_logs.py`验证运行未结束时可见和成功/失败原日志不变。真实公开EF探针`run-575b16b057aa47f8b04a46adb4a9a857`在native仍running时已读到两个输出流，结束后原始文件逐字节一致；探针只验证管理能力，不是设计PPA实验。单元391项与24子测试、Ruff/格式/Pyright/差异通过；含发布资产的完整回归以最终运行回执为准。

Goal完整回归最终414项、24子测试通过（929.41秒），检查点`c17139f`；真实公开探针的leaf源码hash与提交一致。旧活跃Goal轮次未注入更新。

现有`admin/goal_route_control.py`增加对完成的原生timing-only baseline的匹配控制，继续保留全部转换、placement、route、报告和二进制，只在单独对照脚本中省略明确的单行修复调用；原固定源码功耗控制保持。`admin/test_goal_route_control.py`新增两项，修复前2失败/4通过，修复后6通过；验证原输入/二进制/目标/producer/输出位置及原文件hash不变，静态/格式/类型通过。不是新增专业方法，也不把省略修复的脚本称为原Goal。

没有新增harness、数据库、服务或公共接口，没有改专业算法、评分、晋升、活动副本及profile。原EF队列修复与本次Toolkit更新只在所有消费者安全空闲后备份原位部署；gateway和实际adapter使用两个不同wheel环境，均需核对。原端口、状态路径、WAL/FULL及DF保持，不提权或移动系统目录。

## 未完成与下一步

原Goal最终在原28800秒原生调用监督下以TimeoutExpired失败；最后保存的原前端身份均已退出，收尾核查未发送信号，根人工恢复累计仍6次。原项目`Contest2026Evaluator._measurement_lock`有意串行物理评价，避免运行时间受并发干扰；Student3在11:13:09 UTC已构建成功，却在等待该锁时耗尽执行预算，不能记为EF丢失任务。保留原串行评价政策，后续完整预算须覆盖各Student及原生收尾。预算耗尽后仍启动的工程修复推理成本保留，统一前端截止语义列入正式冻结核查。

候选45的Query已回答并核对真实candidate作用域，建议Goal时序恢复；路径级配对缺少部分语义、ECO操作授权未形成正式包等限制完整保留。原Goal终态及全部前端/EF任务结束后，`a24-jpeg-flow45-goal-timing`已用新冻结r3环境启动原timing-only基线算法接力，尚待共同完整布线和PPA交付；它不是新Code源码搜索。Query冷对象导入与约七分钟模型诊断均计成本，不据温态查证称完整效率优势。

JPEG的64GiB单并发SAT完整证明在18:06 UTC以工具错误结束，没有PASS或不等价反例。内核日志明确记录PID2638022在`/user.slice/user-1020.slice`内存组OOM被杀；该账号当前上限99,999,997,952 bytes（约93.13GiB），生产EF配置128GiB超过当前账号上限，且账号另有其他会话占用。不能把它称为不等价或再盲目扩内存。已测新单LTO Code峰值约4.5–4.6GiB、Flow最高7.13GiB；计划在安全空闲时按实际余量校准本轮资源池及新profile，并核查低内存完整证明策略，保留全部输出/分区验收，不动其他会话、不提权。

此失败还复现根`jobs.leaf`在native非零退出后复制缺失PASS、再次触发FileNotFoundError。最小修复只跳过失败命令的缺失声明文件，登记`missing_output_files`，保留原退出码和已有产物；成功命令缺必需产物仍失败。新增`admin/test_leaf_failure_outputs.py`修复前1失败/1通过，修复后2项、根368项和静态/格式/类型/差异通过。公共签名、成功manifest、证明标准及原失败证据不改；配合Toolkit失败托管的实际在线验证仍待生产安全更新。

1. Goal完整414项/24子测试、根366项回归及静态/格式/类型/差异门禁通过，模块先发布、根固定版本；当前生产仍未安装EF队列及失败产物修复。
2. 观察原Goal剩余轮次和JPEG完整功能证明至其原终态；正确区分原生预算、算法计算、排队和数据成本。旧前端不注入修复，必要收尾按事先保存的PID/启动标识核验。
3. 安全空闲后更新本轮EF及实际Toolkit环境，真实验证资源不足队首后的GCD任务消费、取消释放、失败日志托管，以及GCD七PPA/DF/SDK同值。
4. 新冻结专业环境，完成有证据的JPEG时序接力、完整搜索预算校准、完整输出证明和独立重放。失败批次事实、固定方法接力与新搜索分别报告。
5. A25之后再运行公平PPA与完整平台操作对照。当前不足以声称团队全面胜过最强单项或端到端token/时间优势。

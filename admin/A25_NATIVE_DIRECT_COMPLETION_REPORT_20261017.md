# A25：原生Codex完整验证操作资格

原生Codex直接操作路径已完成共同FF测量、全部18输出PDR证明、从RTL开始的第二次独立完整ORFS及再次共同测量。根Agent独立核对原始产物后通过；两次七PPA逐值相同，也与此前平台控制相同。它解决直接侧操作资格，尚不构成平台效率或团队PPA优势证据。

## 实际任务与独立证据

- 用此前已经独立验收的原生完整GCD输出作明确输入；本次没有声称重新执行第一次完整流程。
- 同一0.159.3原生CLI、gpt-6.1-sol/medium及本账号权限，使用原SIF、固定库顺序、显式ps的310ps SDC和相同共同测量/证明模板。未使用裸模型循环或新增Agent harness；直接对照资格按计划调用原生工具，平台专业任务的EF入口不改。
- 实际EQY合并分区只有原顶层输入，无crossbits；覆盖req_rdy、resp_msg[15:0]、resp_val全部18位。原始SV有对应断言，实际引擎为ABC PDR，SBY状态`PASS 0 0`、engine日志`Property proved`及EQY PASS均核实。
- 独立完整重放从空WORK_HOME开始，实际make使用原设计配置、NUM_CORES=8及逐字节库/SDC；原始综合、floorplan、placement、CTS、GRT、DRT和finish阶段记录均存在，最终DRC为0。其间未预填原结果或阶段checkpoint。
- 从两份原生测量JSON及唯一report_power Total第四列独立取值，七项逐值相同：setup/hold TNS为0，setup WS 0.00934292ns，power 0.001373553765W，cell/core/die面积42.6757/58.7866/78.4819µm²。布局与电气违例为0；208份产物哈希、37份输入及26份用户工作保护检查通过。

## 成本与失败

原生收据完整：输入1,180,582、输出7,977，合计1,188,559 token；缓存输入1,115,008为输入子集。墙钟191.167048秒；记录器user/system为2.38/0.97秒，已回收原生后代为133.2/12.1秒。独立服务、远端模型与未回收后代不在该CPU观测范围，根Agent的准备/核查推理成本未知，不记零。

原生CLI一次调用包含内部Agent循环，上述token是其实际用量；不能把一次CLI调用称为一次服务端推理请求。新准备账本r6明确该计数语义，并延续此前所有准备成本。

容器缺rg的只读查看失败127由原生Codex自行转用grep恢复，原事件和成本保留，未进行外部episode修补。独立核查脚本首次误要求SBY状态文件只有`PASS`，实际格式为`PASS 0 0`；原误判日志保留，按原生格式和实际Property proved/EQY结果复核，没有重调模型或EDA。

## 实验范围与后续

原准备建议等待所有任务后串行运行；本次在JPEG等待窗口执行这项小GCD资格任务。实际账号内存限约100GB、启动时使用约74.4GB，参考此前GCD实测，不并发Code构建、不动服务、资源池或活动JPEG副本。共享争用保留在实际墙钟；正式计时试次仍串行。

该任务明确复用第一次完整输出，并且JPEG同时运行，不能将它与此前平台操作的token/时间相除后宣称节约。正式任务须让两侧从相同起点承担相同完整工作量，并补齐匹配专业动作/实际交接/恢复。JPEG完整轮次、健康Code接力和预算校准、生产Gateway实际更新、A25冻结及A26–A28仍待完成，老板业务验收独立。

现场证据：`var/business/a25-formal-preparation-20261017/native-direct-completion-r1/`保存事件、收据、完整workspace；`native-direct-completion-r1-independent-acceptance.json`及同名audit日志是独立核查，首次格式误判另存`native-direct-completion-r1-independent-audit-format-assumption-r1.log`。`preparation-costs-r6.json`链接前序准备账本。

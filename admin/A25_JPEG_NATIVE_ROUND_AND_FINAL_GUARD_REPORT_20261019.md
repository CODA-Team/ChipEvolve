# A25：JPEG完整原生轮次、收益归因与最终约束

原JPEG Goal一轮四Student及Teacher评审已实际完成。原生选择Student03，其共同测量、OpenDB/ORFS/OpenSTA三类事实和公开SDK七PPA核对已通过；但原setup约束失败，不能采用。其余三个候选的共同交付仍在进行，健康完整Flow等原后继继续等待。A25未冻结，A26–A28未完成。

## 已核验的业务结果

Student03共同最终功耗155.27968109mW、单元面积6378.88µm²、core9048µm²、die9854.14µm²；setup TNS为−0.766489ns、WNS为−33.0878ps，hold TNS为0。相对原业务目标，`setup_tns_ns_min=0`这一约束失败。功耗/面积改善不能抵消这项失败，原生`validated`也不授权业务采用。

证据不是只读本机输出：公开EF `run-223f28b47aea44dc957478febc5d3d28`的注册归档已核对，原生JSON、原测量Tcl及唯一report_power Total行重建七PPA，与宿主后处理值同值。三类数据快照的design/run身份和ORFS七值再由公开SDK逐项核验；原目标保持原字节。候选物理producer为`run-7c383028ccae4cc9bf6c1899c641c464`，完整共同DRT/RCX为`run-b5d8316b752649b4add2ac66e36e4414`。

当前父结果的候选交付元数据仍可能收尾，不能把此时观测的result哈希当作后继冻结身份。新观察明确保留这个限制；全部候选最终清单和可行性由原只读观察器继续核查。

## 是源码收益，还是配方收益

原算法自身已完成匹配父项控制`run-035a965018534c439053aebc8e56d90e`。四Student及父项的Tcl除输出目录相同；都是原`repair_power`加`last_gasp_deep`配方，没有平台缩减原配方预算。实际注册物理/解析归档和输入SHA、二进制/构建收据、701份声明源码逐项核对，四候选只改SetupLastGaspPolicy.cc，父项无源码差异。

| 原生局部结果 | 父项及Student01/02/04 | Student03 |
|---|---:|---:|
| 总功耗mW | 162.536367774 | 162.541836500 |
| setup TNS ns | −5.329224110 | −5.253526211 |
| 最差slack ps | −36.108784378 | −37.605918944 |

Student03改善总负裕量，却使最差路径和功耗略差；原生综合目标仍认为它有局部价值。其机制确实进入、提交并保留动作，不能解释为“平台吞掉了所有源码改动”。Student04机制被触发，但指标未改善；01/02原判定为未触发、收益0。注册ODB字节进一步证明01/02/04与匹配无改动父项完全相同，四个源码候选只有两个物理状态。

这解释了本轮部分收益为何不能相加：专业局部判据、机制激活与最终业务可行性是不同事实。上述表是原生局部实验，不能代替共同最终PPA或正式团队优势。原Teacher/Student/筛选规则保留，平台用共同事实和原目标拒绝不可交付分支；没有为了得到正面结果改评分、换基准或删候选。

## 原生完整性与费用

原round.json和四份candidate/evidence齐全；四份均通过原build/flow/metrics/placement/lec检查，原生integrity均通过。所有13份调用收据与实际invocation、完整events及原ledger核对，实际角色均为gpt-6.1-sol/xhigh。

- 可见原生Codex调用13次，含Teacher、Student、反思与两次telemetry修复；后台HTTP请求数不可直接观察。
- 输入8,041,396、输出131,162，合计8,172,558token；缓存输入6,983,936是输入子集。
- 原生operations目录48个EF任务均成功，采样CPU合计21,749.96秒。这不包括共同最终交付、候选补测、后续验证、服务或主Codex。

`preparation-costs-r47.json`逐份核对前46个费用快照及其哈希，新增这13次可见调用和48个唯一EF任务，无已记任务重复累计。原生局部收尾不是整场费用已完整；所有正在交付和后续成本继续单列，未知费用不填零。

## 实际运行软件身份

四个相关解释器内23份非editable安装包、296份Python代码与安装RECORD核对。实际EF/DF仍为3936549/3537663，PID/start ticks与原记录一致，应用安装先于这两个进程启动；软件记录来自实际服务环境，没有把用户未部署的DF/DI源码修改当作在运行版本。

解释器/角色的软件版本分列，不假定它们全部相同。Toolkit和SDK按实际wheel/代码字节记录；缺失wheel来源SHA时保留未知，同时固定已安装代码/METADATA/RECORD。服务生命周期与磁盘指纹不是进程内存模块检查。本轮没有安装包、重启服务或修改活动输入。

## 交付与剩余工作

证据在`var/business/a25-jpeg-native-mechanism-audit-20261019/`：`original-round-native-closure.json`、`registered-native-initial-four-matched-recipe-audit.json`、`registered-native-checkpoint-equality.json`、`selected-common-registered-setup-failure.json`、`selected-sdk-common-rejection.json`。实际软件记录在`var/business/a25-runtime-software-identity-20261019/`，费用为`var/business/a25-formal-preparation-20261017/preparation-costs-r47.json`。

两个新增只读分析脚本通过Ruff F/I、格式与Pyright；实际注册产物/安装记录核查通过，26份受保护用户文件保持。初版取证器曾错误要求物理任务归档包含后处理CSV及metrics.json，已按真实物理→解析阶段修正并保留解释：原CSV解析会追加，必须取绑定正确日志的注册解析任务最后一行；共同七值从注册原生JSON/功耗报告重建。没有为修正取证格式重复模型或EDA，也没有改专业解析或数据服务。

下一步继续全部候选共同交付及原约束/SDK核对，保留失败；随后实际健康Flow2×50、原生专业参考和Flow→Query→Goal接力。正式PPA团队允许累计完整专业投入；正式操作对照仍需相同完整业务、明确直接侧边界/初态/故障收尾和冻结的独立验收。当前还不能称正式就绪。

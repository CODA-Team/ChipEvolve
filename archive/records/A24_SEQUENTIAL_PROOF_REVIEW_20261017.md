# A24：寄存器状态切分与验证器负例核查

JPEG完整输出证明尚未通过，完整Flow仍未启动。此次调整验证准备与配对，专业算法、目标、物理输入及服务保持。不能把下述小电路检查当作JPEG等价或协同PPA收益。

## 现场证据

上一份声明层次匹配尝试`run-af2e6d20c02c4ac89721dc2a7b1e7156`在约2005秒时仍生成分区，已产生约22.18GB中间文件。采样`size[3]`分区分别带入297716/298000个gold/gate单元，接近整个展开模型。两份原网表有4384个同名、同master的寄存器；其Liberty内部状态没有包含在仅“端口和原声明层次线网”的配对中。

保存原配置、配对、日志、采样分区和原实例清单后，通过公开EF停止本次成本预演。它不是OOM、deadline到期、功能反例或证明成功。原记录、原产物与前一份配对假失败证据均保留，Flow门槛正确拒绝启动。观察回执位于本片`declared-proof-decomposition-observation/receipt.json`。

使用同一固定ASAP7 Liberty、两个反馈寄存器、全部输出的原生探针：

- 旧SAT路径`run-97efcf3c7b794967b0583a2f81ea1969`把故意改错的时序电路也判为PASS，探针因此失败。该结果不得用作正确性依据，尚未定位SAT内部唯一原因；历史收据不回写。
- 原生SBY/ABC PDR及固定Z3路径`run-aa54c33c799547f2b86fd501ecf37418`对正确电路PASS、错误电路FAIL。新增状态切点后，最大单侧分区从9单元降为6单元，所有输出仍被验证。这个规模变化只说明小电路机制，不外推JPEG速度。
- 新根生成器从探针实际Yosys JSON中得到`reg0.IQN`、`reg1.IQN`，生成的正反例配置与真实已运行配置逐字节一致。

正式验收使用通过此时序负例核验的PDR路线。新EQY验证入口在提交EDA前明确拒绝旧SAT；已有历史回执不回写，配置生成函数仍保留SAT以便核查原探针，不能据此签发新通过回执。GCD/AES拟交付结果也须复核：AES既有证明为EQY/SAT，直接受本次资格失败影响；GCD既有证明来自独立Yosys路线，本探针没有证明该路线同样误通过，安排PDR复核用于交叉确认。旧物理PPA、数据身份与独立物理重放证据保持，但不替代功能证明。

## 最小实现与边界

- `chip_evolve/logic.py`：显式私有`validation.equivalence_match_flops=true`时，在原解析任务中导入同一固定Liberty，取得实际单元逻辑模型；要求EQY/PDR。缺省原解析脚本保持，旧配置/实验不升级。
- `chip_evolve/eqy.py`：仅对两侧同实例、同master、相同逻辑定义，从Yosys实际FF的Q位选择一个公开状态别名；每个状态仍是待证明的匹配点，不是假设它已经相等。用一个精确正则规则登记这些状态，避免逐状态重复扫描全表。自动路由网名不恢复为匹配点。
- `admin/test_eqy_sequential_state.py`：核验实际FF与buffer/clock区分、改名/master/模型差异不匹配、旧解析不虚构状态、PDR要求、EF托管状态与solver证据，以及显式/缺省解析边界。

数据流仍是根验证准备→原EQY/SBY/ABC→公开EF及证据→完整输出/每分区PASS核验。没有新增后台、数据库、通用harness或公共API，未部署用户DF/DI/evaluation修改。

下一次JPEG独立尝试保持同输入、Liberty、全部27输出、xprop、固定solver及4小时上限；状态切分与并发属于显式配置。通过前不启动完整Flow、不采用JPEG候选；后续完整原生轮次与公平实验分别验收。

新接点27项针对检查、根399项回归、改动文件Ruff及全根格式/类型检查通过，26份保护文件SHA保持。全根Ruff另发现三个既有文件中的五项检查问题，已单独质量收尾：`code_evidence.py`整理导入并以`max`等价表达原排序取最大值；`native_process.py`仅整理导入；`dpl_case.py`显式绑定同步正则回调的替换文本。接口与运行行为保持，没有放宽检查规则。收尾后全根Ruff、32文件格式、全根类型及399项回归（16.39秒）通过。

旧SAT业务入口拒绝检查修复前复现失败，修复后28项相关检查、根400项回归（16.48秒）以及完整Ruff/34文件格式/类型检查通过。预算边界测试改为实际合格的PDR调用，仍核对缺省/显式时限、内存、并发、完整输出、父来源与目标，未以跳过测试替代核查。新JPEG尝试`a24-source-integrity-proof-pdr-state-r1`实际识别4384个模型状态点，4个worker共享原4核/32GiB/14400秒；完整证明未结束。

## 本轮改动文件清单

| 文件 | 职责与本轮改动 |
|---|---|
| `chip_evolve/eqy.py` | 固定模型状态匹配、证据托管与拒绝旧SAT新签发 |
| `chip_evolve/logic.py` | 显式模型解析及提交前验证路线核查 |
| `admin/test_eqy_sequential_state.py` | 模型状态来源、匹配范围、解析及托管边界测试 |
| `admin/test_eqy_pdr.py` | PDR原门禁及旧SAT拒绝回归 |
| `admin/test_local_eqy.py` | 在合格后端继续验证实际期限、资源和完整输出 |
| `chip_evolve/code_evidence.py` | 既有静态门禁整理，候选来源选择含义保持 |
| `chip_evolve/dpl_case.py` | 显式绑定正则替换文本，设计配置含义保持 |
| `chip_evolve/native_process.py` | 仅导入顺序整理 |
| `ARCHITECTURE.md` | 记录私有配置、数据流及验证路线边界 |
| `PROJECT.md` | 更正当前功能验证资格与业务结论范围 |
| `TASKS.md` | 记录当前预演、验证与后续门槛状态 |
| `SOURCE_MANIFEST.json` | 更新根实现检查点，模块版本保持 |
| `admin/FORMAL_EXPERIMENT_PROTOCOL_20261016.md` | 模型间接依赖、原生Codex双侧操作及功能资格口径 |
| 本文档 | 原生观察、失败、修复、检查与改动清单 |

运行脚本、原始记录及准备清单均在`var/business/a24-jpeg-pilot-20261016/`，不发布为产品源码。26份用户文件及所有专业子模块原修改保持，不借用受保护的evaluation工作。

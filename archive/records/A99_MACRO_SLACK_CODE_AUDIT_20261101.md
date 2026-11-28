# A99：Macro案例、真实slack分布与代码质量核查

日期2026-11-01；根基线`c59636e`。本轮按老板三项问题开展审查和必要短验证，没有修改产品源码、历史PPA、目标约束或专业算法，没有新优化/路由/模型搜索，没有重启EF/DF。运行证据与交付位于`var/business/a99-macro-slack-code-audit-20261101/`。

## 一、结论与业务含义

1. **跑过带宏案例，但未找到本批实验中已完整验收、收益显著的带宏优化正例。** Ariane两套PDK实际均为136个SRAM宏；ASAP7仍有时序问题，Nangate45最终仍有电气问题。不能拿漂亮宏布局截图代替优化成功。
2. **GCD/JPEG支持真实slack分布图，已经用共同OpenROAD GUI导出。** 本轮交付5个状态各setup/hold两张，共10张原生PNG、逐端点TSV与两页原图拼版PDF。参考图的电压缩放与活动频率分类没有对应实验数据；现有图应解释为端点最差slack分布。
3. **基础代码和主链回归可用，但审查新增两处可复现结果校验缺口。** 采用时未重新绑定物理文件字节、NaN可被标为可行；另有测试文件静态门禁欠账。只读审查没有将这些问题记为已修复，也没有据此断言历史实验已被污染。

## 二、Macro实际结果

直接通过EF读取三份Ariane ODB，检查`BLOCK*`实例、master与包围盒；不根据设计名称猜测有没有宏。

| 状态 | 实际宏 | 模型 | 宏包围盒面积µm² | 当前结论 |
| --- | ---: | --- | ---: | --- |
| Ariane/Nangate45 baseline | 136 | fakeram45_256x16 | 429083.536 | 实际完成参考 |
| Ariane/Nangate45 A84最终RCX | 136 | fakeram45_256x16 | 429083.536 | setup/hold、DRC通过；slew1/cap60，未采用 |
| Ariane/ASAP7 A55原最终来源 | 136 | sram_asap7_16x256_1rw | 19100.928 | 原setup TNS约−127.168ns、slew444；未采用 |

Nangate45两状态的宏名称、master和包围盒记录逐字节一致，说明这条链没有改变宏位置或尺寸。该案例是带宏设计上的标准单元/时序优化，不能称作宏布局优化。ASAP7 SRAM源来自FakeRAM2.0，只提供LEF/Lib抽象；原A60已核实缺内部GDS几何，本轮保持此边界。

Nangate45实际baseline→A84最终指标：

| 指标 | baseline | A84最终 | 变化 |
| --- | ---: | ---: | ---: |
| 总功耗mW | 159.35091674 | 159.34552252 | −0.003385% |
| 单元面积µm² | 739938 | 739092 | −0.114334% |
| setup WS ps | +206.953 | +288.494 | +81.541ps |
| setup/hold TNS ns | 0/0 | 0/0 | 保持闭合 |
| slew/cap违反 | 16/252 | 1/60 | 明显减少，最终仍不合格 |

baseline本身有16项slew、252项cap违反，优化后减少到1/60，电气修复有进展但尚未清零。本轮未重新执行Ariane完整STA；两组值及拒绝原因逐项回到原`result.json`、A84`terminal-inspection.json`和冻结目标核对。Ariane/ASAP7 A62同协议GRT曾有11.24%的局部TNS债务减少，但尚非最终合格收益；A64后续也未闭合。本轮没有用跨RC或跨阶段数据计算宏优化收益。

GCD F37/G02和JPEG JB0/JG3/JP3实际宏数均为0，适合展示标准单元、功耗、时序变化，不应画入不存在的SRAM宏。

## 三、能画什么slack图

共同镜像的GUI实际提供：

```tcl
gui::show_widget Charts
save_histogram_image /absolute/output/setup.png -mode setup -width 1600 -height 900
save_histogram_image /absolute/output/hold.png -mode hold -width 1600 -height 900
```

先在空白共同版本窗口加载同状态Liberty/ODB/SDC/SPEF和传播时钟。交付`viewer/*-load.tcl`保留实际读取命令，不含优化或exit；不能在已加载ODB的窗口重复read_db。

原生Charts由STA端点集合取每端点最差slack，纵轴为Number of Endpoints。本轮同样遍历`sta::endpoints`，分别取`get_property ... slack_max/slack_min`，未只取最差50条路径、未枚举所有组合路径、未拟合钟形曲线。无约束/无限值保留并单列，不填零。读数精度约0.001ps；独立原生WS/TNS全精度另存，按端点精度核对最小值和负值之和。

| 状态 | 受约束setup端点 | 负setup端点 | setup WS ps | setup TNS ns | 非负且≤5ps端点 |
| --- | ---: | ---: | ---: | ---: | ---: |
| GCD Flow F37 | 53 | 0 | +12.289031 | 0 | 0 |
| GCD Goal G02 | 53 | 0 | +0.083406 | 0 | 16 |
| JPEG baseline JB0 | 4476 | 0 | +19.504232 | 0 | 0 |
| JPEG Goal03 JG3 | 4476 | 19 | −12.585267 | −0.07011425 | 31 |
| JPEG最终JP3 | 4476 | 0 | +10.230261 | 0 | 0 |

GCD原STA共56个端点，其中3个setup/hold无约束。JPEG共4497个端点，setup无约束21个，hold无约束113个；每种检查的统计分母分别处理。JPEG受约束hold端点4384个，三个状态均无负hold端点。

这些图支持的机制是：GCD为功耗/面积回收使用了时序余量；JPEG源码优化产生19个负setup端点，选择适当后续修复后全部闭合。GCD没有证明将critical wall变成更安全的gradual slope；参考图中的降压曲线还需要多电压库/扫描，Frequently/Rarely exercised还需要工作负载活动证据。本轮没有这两种数据，不把默认vectorless功耗活动率当作真实路径活动频率。

原生GUI对每图自动选箱和坐标范围，不能直接把不同宽度的柱高当作统一分箱对照。需要叠加比较时，可从本包TSV统一分箱，用标准科学绘图工具作图并注明数据来自OpenSTA；它与原生GUI导出应分开标注。交付PDF原样嵌入GUI图片，不重画图中数据或补造曲线。

## 四、代码质量：实际检查结果

| 范围 | 本轮结果 |
| --- | --- |
| 根业务 | 770 passed，32.08秒 |
| EF | 396 passed，1个条件跳过；依赖检查与mypy通过 |
| DF当前含用户WIP | 378 passed；依赖检查通过 |
| DI当前含用户WIP | 13 passed；依赖检查通过 |
| Query | 228 passed；Ruff/格式/严格Pyright和3条依赖约束通过 |
| Toolkits | 78 passed；依赖/F类静态通过 |
| Flow | 99 passed；依赖检查通过 |
| ECO | 67 passed，2 subtests passed |
| Goal实际goal_python环境 | 459单元测试passed，71 subtests passed |
| DPL | Python编译、shell语法、33知识索引、repo hygiene通过；明确跳过Teacher dry-run和新实验 |
| 根产品Python | Ruff、格式、Pyright通过 |
| 根全部业务测试静态范围 | 11条lint诊断、2文件格式不通过，不能写成完整静态门禁全绿 |

Goal第一次误选旧U4模板解释器，全套中出现1项缺`eda_toolkits`失败；独立定位仍复现。核对源码实际使用的`goal_python`后，改用当前运行环境完整重跑459项单元测试全部通过，当前环境存在Toolkits/client/contracts。第一次全套里的归档测试17项通过/3项跳过；没有把旧环境缺包说成当前专业算法错误，没有安装包、改源码或伪造全套单解释器通过。完整日志随包保留。

九模块HEAD与WIP记录在`module-heads.json`；DF当前HEAD与根manifest不同，DF/DI都有既有修改。这是原有工作区状态，本轮完整保留，运行服务也未切换。测试通过的是所列源码/解释器范围，不能代替服务已发布或PPA业务验收。

### 新发现P1：物理文件在验证后改变，采用检查未重新拒绝

位置：`chip_evolve/selection.py:54`，尤其95行之后只核对proof input hashes。

当前检查绑定result/reference JSON SHA、目标条件、证明与七指标重放，并校验证明输入的网表/库，但没有在该入口将候选`files.odb`和`files.spef`重新绑定到已测量/已验证字节。合成夹具中，原验证可读后，只改ODB和SPEF，不改result JSON/网表/证明，`checked_validation`依然接受。

这意味着文件误覆盖时，采用记录可能对应旧指标而路径指向新物理状态。重现证明校验缺口，不证明任何历史采用已污染。本轮8份真实来源、GUI读数和原件核对均没有发现这种污染。

建议在现有验证回执/测量证据上绑定并核对ODB、SPEF及相应SDC字节，继续复用现有EF登记SHA；增加“验证后改文件必须拒绝”的针对性回归，不新建数据库或重新优化历史设计。

### 新发现P2：NaN可绕过约束比较，向上层返回可行

位置：`chip_evolve/selection.py:21`的普通大小比较，以及`comparisons.professional_facts`根据空失败列表产生`final_feasible=true`。

将合成候选的power、setup TNS或cap违反计数分别设置为NaN，三次都得到空失败列表和`final_feasible=true`。Python NaN与阈值的`>`/`<`均为false，故普通比较不会拒绝。完整采用的其他环节可能继续拒绝，不能把本重现夸大为NaN已进入论文；实际五状态原值均有限。

建议只在现有结果入口校验必需指标为有限数，非法值明确报告“指标无效”，保留原数值/单位和业务阈值；增加三个针对性回归，不添加通用防御层。

### P2/P3：图像入口及静态欠账

- A97冻结图包的`view_gui.sh`使用`--cleanenv --no-home`却未显式传DISPLAY和Xauthority；它不能作为普通VNC中可直接打开窗口的可靠入口。A98新增的启动器已显式传显示与认证，并给出空窗口逐条加载命令；旧ZIP仍保持原样，后续补发修正入口时不要改原PNG/输入/历史SHA。
- 11条root lint在测试文件，主要为导入顺序、嵌套with、未用变量和dict写法；格式欠账在`admin/test_overnight_data.py`、`admin/test_overnight_runtime.py`。产品Ruff/格式通过。建议单独清理，不与结果语义修复混提交。
- DF的大对象解析/持久化延迟是A88已确认的未闭合问题，本轮未做新性能结论；不以当前单元测试通过宣称延迟已修复。

## 五、建议的下一步

1. 先在现有selection/validation边界补物理文件字节绑定与有限指标检查；一项缺口一组针对测试，保持历史结果只读。
2. 补发正确VNC启动入口，复用本轮原生Charts命令和既有图像包，不重做PPA。
3. 论文优先用JPEG的19→0负端点展示源码优化与物理修复，GCD展示功耗收益与时序余量交换；带宏案例如要写优化正例，优先解决Ariane/Nangate45现成分支的电气资格，再单独验收。

不启动大规模新benchmark，不为了画参考曲线改变时钟、供电或活动率，不增加平台服务/API/评测数据库。本轮为审查与真实只读图像交付；新缺陷修复仍待实施。

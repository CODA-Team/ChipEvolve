# A48：Ariane 原14组动作与完整GRT收尾验证

接续根 `d86f63e`。本切片无产品源码改动，复用A34已通过的兼容适配；长专业搜索仍暂停。

## 实际验证范围

原Ariane/Nangate45 replace-buffer脚本此前只完成两动作短验证。此次使用同一原件，先通过DF/DI逐一核对14个驱动对象身份，再完整运行原14组换单元/BUF_X4插入，以及原 repair_design、条件式 repair_timing、Diamond合法化、增量GRT与RC估算收尾。未改变选中驱动、替换单元、修复策略或参数；诊断输出迁到新目录，原件保持。

EF `run-ca9fce0e3e7443c9a7bf643e4d6c33e1` succeeded。实际OpenROAD退出0、工具段221.09秒，14个显式buffer及新增net断言通过，repair_design和原完整收尾标记通过，无EST-0104或崩溃；输出ODB/V/DEF由原EF登记。原生repair_design另报告400次resize、582个buffer，不能把这些额外动作误算成14个显式插入。

## 观察与业务边界

| 观察位置 | RC口径 | setup TNS | setup最差裕量 | slew违反 | cap违反 |
|---|---|---:|---:|---:|---:|
| 原输入 | 原详细布线提取SPEF | 0 ns | +38.8933 ps | 416 | 713 |
| 本次原脚本收尾 | 新GRT估算 | 0 ns | +275.1168 ps | 4 | 8 |

两行寄生模型不同，**不可据此计算最终时序/电气收益或认定最终PPA改善**。它证明已知失败的原动作链现在能完整执行，同时明确仍有4项slew、8项cap违反；没有DRT/RCX最终PPA、hold核验、完整功能证明或采用。也不是新一次专业Agent搜索。

## 执行与事实回流

原工具日志及其EF登记SHA核对通过；GRT诊断值经现有ORFS事实适配器→EF→DF→DI完成回流，快照 `a48-run-ca9fce0e3e7443c9a7bf643e4d6c33e1-grt-native-unit-bound`，scope/revision及全部原值一致。只导入阶段诊断摘要，不伪造最终PPA或复制完整对象库。

第一份私有诊断元数据漏写时间单位，DF正确标partial；在新元数据/新快照中补入原脚本明确的1ns声明，不改旧快照、不重复工具执行。原生日志、完整事实输入及前后记录均保留。

## 发现的下一处具体阻断

单位已补齐的事实在DI可读，但安装包Query精确TNS查询仍为NEEDS_MORE_DATA，理由为metric source artifact is missing。DF证据明确指出原始元数据属于独立导出run，而指标的subject是实际物理run；Query查找/引用原件时仍混用了这两个身份。原失败响应和两个真实run/原件SHA已留存。下一切片据此修Query的真实原件归属，不放宽snapshot/revision检查，不改成无证据回答；无需重跑Ariane。

## code-check与文件

原14个replace选择和完整repair/legalization尾部对比通过；4项既有针对回归、Ruff/格式/Pyright通过。根产品源码与A47的712根回归检查点相同，复用该完整回归；26个用户保护文件、原源result/ODB/SDC/SPEF/脚本与适配器SHA保持。未新增服务、公共接口或修改专业算法。

仅本报告、TASKS与STATUS记录状态；运行脚本/日志/收据在 `var/business/a48-ariane-full-grt-compatibility-20261025/`。关键文件为 `full-recipe-check.json`、`source-code-check.json`、`native-unit-bound-facts-receipt.json`、`native-unit-bound-DF-metrics.json`、`query-unit-bound-TNS.stdout`。工程兼容验证通过，待老板业务验收；Query上述阻断与正式双次结果仍未完成。

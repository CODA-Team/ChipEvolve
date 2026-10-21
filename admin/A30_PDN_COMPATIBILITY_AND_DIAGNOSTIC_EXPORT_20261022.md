# A30：供电网兼容修复与诊断数据导出

本轮已找到并局部验证 Ariane ASAP7 的实际供电网修复，启动新的完整物理来源；八组双次合格优化尚未完成。专业算法、平台公共接口和服务配置未改。

## 实际供电网对照

原详细布线后的最终供电检查确实失败。先前在 pre-PDN 布局上运行完整实例检查，又包含了源 DEF 中尚未重新布局、合法化的单元，产生上万条与最终告警不同的实例短接/悬空告警，不能用它判断条带修复无效。

本轮复用两份已经生成的 PDN，使用 OpenROAD 原生 `check_power_grid -floorplanning` 检查该阶段的供电图及固定实例。实现源码明确在此模式跳过非固定单元，并保留供电图连通检查；没有增加第二种网格参数或重跑优化。

| 原生 floorplan 检查 | VDD | VSS |
|---|---|---|
| 原 M5 offset=0.300µm | 失败 `PSM-0069` | 通过 |
| M5 offset=1.380µm | 通过 | 通过 |

真实 EF 为 `run-f532a20e8668414c99be7ca15716ec44`。条带宽度、间距、周期、宏网格与输入布局保持，只移动 M5 供电条带相位。此结果证明阶段性的网格修复，尚未证明完整流程、最终 DRC/供电或 PPA 通过。

新完整来源 `a30-ariane-asap7-pdn-compatible-orfs-baseline-trial1` 已交给 EF：`run-2c6a562e2c6c41ea9a63f564c59409ab`。使用原映射网表/宏布局、原 0.9ns、21 份原标准单元/SRAM 库及原目标，供电修复作为显式冻结输入；正常最终供电检查继续开启。不是 RTL 综合基准，不与旧失败试次拼成成功均值。

旧 ECO 会话 `run-62442a4e27f747d4a3cdc1596e0f9efd` 在 queued、零 attempt 时取消，避免继续消费已知供电不合格的来源。原失败、原配置和取消原因全部保留。新固定工作清单在完整来源交付后执行 DF/DI/Query，再启动原生八轮 ECO，先审首个结果质量，再独立重复合格协议。

## 时序事实与失败状态一起保留

旧失败流程已完成的 ODB/SPEF 经原 EF 登记产物取回、哈希核对、共同测量和 DF/DI 发布。真实 DI 指标为 setup WS=-0.285396ns、TNS=-155.146ns；hold TNS=0，功耗642.41528511mW、单元面积43672.8µm²，与原参考相同。测量任务 `run-3d7a4f0f61354edd931572f6d903a2ab` 成功，不代表原供电失败的流程成功。

私有诊断请求最初漏了导出所需的 `capability` 字段，导致一次论文导出失败，已有快照保留。已补齐诊断类型；`admin/paper_relay_paths.py` 现在根据结果中实际的 `original_flow_status=failed` 将诊断明确标为“失败流程的测量、不是合格重复、未采用”，不会被局部 `status=succeeded` 覆盖。

新增集成测试从真实收集入口验证该场景：成功的测量与失败的原流程并存，负时序数值、原件及拒绝状态全部导出。现有 Ibex 证明测试补充返回值非空断言，使同一文件的类型检查通过，不改变验收逻辑。

实际 PDF/CSV 已重新导出；CSV 中诊断行明确为 `diagnostic measurement of failed flow; not a qualified repeat; not adopted`。旧快照不改写。

## 其他真实进展与验证边界

- JPEG Nangate45 原 Student1、Student4 链接均成功，真实 EF 分别为 `run-6a5aac77543446e0b13a2b9078300954`、`run-3fafd24b460a4fc5a2e930928af73b68`。不代表完整四 Student 搜索或最终 PPA 已通过。
- GCD Nangate45 原 Flow 的 50 份新布局候选已收尾：27 成功、23 失败，已进入 CTS。失败候选保留，不据此宣称完整搜索完成或找到合格结果。
- Ariane Nangate45 原基准事实交付恢复，真实 Query 后已启动带原 TNS 修复来源的原四 Student 活动。
- Ibex 原真实未完成分区的标准电路化简/PDR 诊断在240秒超时，没有 PASS 或反例，不延长或重复同一策略；完整功能证明缺口保持。
- 原 TNS 真正编译任务 `run-b15e11595d7a4ad9a8b62881268edc33` 仍待调度；不能将版本查询成功说成二进制已完成。

当前根回归命令 `test-env/bin/python -m pytest -q admin/test_*.py`：609项通过。相关 lint、格式和 Pyright 通过；26份保护文件逐 SHA 保持。最初递归收集整个 `admin` 时碰到12个历史 `legacy-integration` 缺失依赖/归档文件错误，因此按当前根测试集执行，没有改历史档案或掩盖产品测试失败。

本轮可审查源码改动仅论文收集器及其测试；本文和任务/架构记录说明实际进度。运行配置、原生 PDN、原件哈希、两次局部检查、新完整来源与工作清单均在 `var/business/a30-four-design-two-pdk-20261021`。用户未提交修改未碰。

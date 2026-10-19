# A25：交接后的 KLayout 导出资格

JPEG 的完整布线任务返回成功，但其 `6_1_merge.log` 有 473,934 条 `Invalid via name`。独立核查发现，交接归档将生成文件摊平到新的 `flow/objects`，其中 `klayout.lyt` 仍引用原 `/work/flow/objects/asap7/jpeg/a19-jpeg-source/klayout_tech.lef`。实际恢复的技术 LEF 在新目录且包含所需 VIA。原 A19 来源导出没有这类警告。

Toolkit `86673fa` 只在已有物理阶段的 `clear_downstream` 中失效两份 ORFS 生成缓存 `klayout.lyt`、`klayout_wrap.lyt`，由原 Makefile 重新生成绝对路径。不改用户模板、技术 LEF、ODB/SDC、专业算法、评分、原约束、公共 API 或数据结构；只读评价路径不调用该清理。格式调整与新增回归限于同一实现文件和测试文件。

## 已完成的验证

- 旧生产 wheel 对新用例为 2 失败、1 通过，候选安装到全新环境后，Toolkit 全部 78 项通过；lint、类型、格式、差异检查通过。跨项目只用 wheel/公开 EF，没有源码路径注入。
- 公共 EF `run-7c75c57a9411493ea23f216407c40e57` 对已完成 JPEG B 布线单独运行原生 `make do-gds`，无效 via 为 0，两个 GDS 各 58,226,282 字节。所有保留的非 GDS results 文件逐个 SHA 同值，原始 zip 不变；没有重跑布线或 PPA。
- 独立只读 KLayout 任务 `run-01b5c0b337c346d181ef8c99fc419f95` 比较真实旧/新 GDS，顶层均为 `jpeg_encoder`、边界均为 `(0,0;99.268,99.268)`、DBU 同值；修复后净补回 1,421,802 个展开图形，没有图层数量退减。此前只读检查器误把昵称 `jpeg` 当顶层名称而失败的 `run-97998aef37974e8fae3f3419065cff86` 保留并计费。
- 首次导出驱动在成功回执写盘之后误用一层 `run_id` 导致打印失败；公开任务和原生导出实际成功，已保存原回执，无重复导出。
- 26 份既有用户文件哈希核对均保持。EF/DF 服务、池资源和专业原轮次没有修改。

原生已有 DEF/reader DBU 警告保留，未凭警告猜测修改单位。这里验证导出缓存修复与几何恢复，**不是 DRC/LVS 制造签核**。旧数字等价和七 PPA 独立重放结论仍成立，但不能拿它们替代 GDS 有效性检查。

## 启用与后继

实现已推送 `modules/toolkits`。完整资格、补导出和启用回执在 `var/business/a25-klayout-checkpoint-relocation-20261019/`；生产是否启用以该目录独立 activation 回执为准，不能以源码提交代替实际 wheel 身份。两份原 DPL 业务重放继续收尾，原后继主管 PID 3147629 暂停派发，计算和模型未暂停。实际消费者收尾且新 wheel 通过后，恢复同一主管，不重跑两个已成功构建。

补导出保留坏的原始 zip 与日志，并为关键结果新增公开 EF 关联证据。所有历史来源的数字/PPA资格与流片产物资格分开；正式试次必须固定实际 Toolkit wheel，并核对最终导出日志，不能仅检查原生返回码。

A25 仍未冻结，A26/A27/A28 仍未运行完成；本修复不证明团队 PPA 优势或端到端效率收益。

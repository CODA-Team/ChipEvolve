# A29：Ibex 派生时钟证明兼容适配

Ibex IP3 的最终物理结果已满足原约束；原全 106 输出证明 `run-b916a1f70b984d4fadba2b6d37bd05ae` 在 SBY 预处理阶段因门控时钟报 ERROR，并未产生功能反例。原失败原件保留，不作为 PASS 或功能不等价结论。

## 最小改动与边界

- `chip_evolve/eqy.py`：既有私有部署配置 `validation` 下增加可选 `equivalence_multiclock`。启用时先在 gold/gate 两侧准备模型时调用原生 `clk2fflogic`，再启用 SBY `multiclock on`；回执明确 clock_model。默认配置保持旧内容。
- `admin/test_eqy_multiclock.py`：确认只增加时钟转换与对应求解选项，不改读入模型、匹配、全部输出义务，且部署配置到生成脚本和回执一致。
- 不能仅给 SBY 开多时钟选项：EQY 在此前会对候选侧做单时钟抽象，派生时钟仍留下不兼容属性。第一份工程夹具捕获此 ERROR，未启动新的完整证明。

不修改 Liberty、设计 RTL/网表、物理结果、专业算法、业务目标或公共 EF/DF/DI 契约；不添加时钟假设、不丢输出、不降为有界 SAT。既有 GCD/JPEG 单时钟配置原样运行。

## 真实工程资格

原生工具均经公开 EF 调度，固定工具镜像和已资格的 ABC-PDR / Z3 身份。成功资格 `run-92b4217757ca46fe94e8a214125eebff` 包含：

1. 门控时钟两位计数器及反码递减等价实现：完整 PDR PASS。
2. 改成错误的反码递增实现：原生 FAIL，产生实际反例 `trace_tb.v`，非工具 ERROR。
3. 原 Ibex 失败的 `mcountinhibit_q.0_DFFE_PN0P_.IQN` 分区：相同分区文件、时钟转换提前后 PASS。

资格回执：`var/business/a29-paper-delivery-20261020/ibex-derived-clock-qualification-result.json`。历史错误与新夹具均保留；工程夹具不计入论文 PPA 结果。

静态 lint/格式/类型检查通过；根当前有效测试目录 573 项回归通过。误将 `admin/legacy-integration` 归档测试一起收集时因归档依赖缺失而报错，未修改归档以绕过。架构检查：只涉及现有根项目内部证明配置，跨模块仍消费已安装 SDK，不增服务或数据源。

## 业务仍待完成

完整 106 输出证明须在单独目录重做；保持 20 GiB / 4 worker / 14400 秒，复用相同已注册 parse 模型和原物理结果。通过后才允许独立物理交付重放、事实核验和既有 select。单分区资格不能替代完整证明；IP3 目前未采用，IB0 保留。

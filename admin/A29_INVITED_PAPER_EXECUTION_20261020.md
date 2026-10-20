# A29：邀请论文案例施工

老板已批准五切片计划：固定 GCD 成果、补齐四专业实际参与、按需扩展 ibex/jpeg/ariane、展示平台操作、汇总论文素材。GCD 优先，10/22 晚目标收口，10/23 前交老师审阅；不以全平台审查清零、完整统计配对或独立 AES 证明为前置。

## 切片一：已完成工程修改，实际业务验证进行中

- Goal 构建归档器修复 `d5a3a95` 已快进合入模块主版本并推送；新实验绑定该正式来源。原有 GCD 结果与验证不重跑、不改写。
- `chip_evolve/native.py`：Goal 原生 TNS 目标读取业务限制（本轮为零），功耗仍沿用原 10% 搜索目标；读取已存在的物理内存配置；ECO 显式八线程，并在新交付记录中声明已完成详细布线。
- `chip_evolve/delivery.py`：只有明确声明已详细布线的新记录走保留布线路径，原检查点保持原语义。
- `chip_evolve/physical.py`：对已布线状态运行 DRC 检查/RCX/共同测量，不清线或重新布线；GRT 检查点仍完成原详细布线。物理任务读取既有设计内存声明。
- Flow `162b80a`：保留 CLI 结构化失败或显式 Error 行，脱敏凭据，不再把所有错误统一写成检查登录。无原生算法/采样/模型重试逻辑改变。

没有新增 EF/DF API、SDK schema、服务或数据库，没有改专业评分/晋升。根新增 `admin/test_invited_paper_relay.py` 覆盖目标与布线交付；`admin/test_eco_pdk_binding.py` 实际执行生成的 launcher，核对显式线程参数。

## 工程验证

- 根当前已跟踪测试及本轮新增测试：549 通过；30 项针对检查通过。
- Flow：从原 flow 工作目录运行完整 test，97 通过。
- Goal：tests/unit XML 450 项，失败/错误 0，原跳过 3；完整 tests 扫描在第三方发布大目录 I/O 上过慢后中断，保留原日志，没有冒称发布产物全审查通过。
- 根产品/新增测试 Ruff、格式与实际安装环境 Pyright 通过。Flow Ruff F 通过；新增函数单独格式化，未批量重排旧代码。整文件 Pyright 仍报告原有四处类型诊断（transport 可空、schema 推断、isfinite 类型、动态 worker 属性），不把它们变成本轮无关重构门禁。
- 首次根/Flow 检查分别遇到旧 Toolkit wheel、缺 Runtime 测试依赖和工作目录错误；已在本轮独立环境安装本机已有 wheel、使用正确模块目录后通过。生产服务和用户 DF/DI 工作树未更新。
- 26 项用户保护文件 SHA 一致；跨模块依赖保持安装 wheel/公开 API。

证据目录：`var/business/a29-paper-delivery-20261020/`。新增本轮独立配置、输入引用和测试环境，不修改历史 runtime。模块提交不等于真实新接力已通过；后续记录实际 EF、PPA、DF/Query 和采用状态。

## 下一步业务验证

1. 已有 GCD routed 产物通过 EF 做一次保留布线的 DRC/提取/测量，确认交付不改变线路。
2. GCD Flow2-37 的原布局检查点启动 DPL 一轮三 Student，复用实际 Query 证据；再对其产物诊断并交给 Goal 一轮四 Student、ECO 最多八轮。
3. 同步准备 ibex/ariane 的实际 RTL/SDC/ORFS 配置，JPEG先复用已有可用候选。平台记录统一，不要求无收益候选成为最终祖先。

本报告后续只补业务结果；不把“已接受排队”写成优化成功。

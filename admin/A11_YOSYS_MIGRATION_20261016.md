# A11 续作：现代 Yosys 完整能力迁移

状态：实施中，待完整实验及老板业务验收。本记录接续 `A11_A12_OVERNIGHT_REPORT_20261015.md` 的部分交付检查点；旧报告不代表本次迁移的最终状态。

## 已确认的边界

老板选择保留原 Flow 的层次化能力，迁移现代 ORFS/Yosys 来源。共同工具版本不变：ORFS `5105b0a77`、OpenROAD `27288f5c90`。现代内置综合忽略原层次旋钮，因此继续标为完整 Flow 能力未通过。

现代默认配置没有定义数值型 LB addon，也未显式定义原 CTS 与两阶段布线参数。未定义的 addon 不是数值 0 或 0.2。本次显式登记 `yosys-full-source-r2`：Yosys、flat 初始点、源 core utilization、padding 0、DPO 1、LB addon 0.2、TNS 100、CTS 25/100，以及独立的 floorplan/final routing 0.25/0.25。它是完整原旋钮的迁移起点，不声称等于默认 ORFS；最终业务上限与默认 ORFS 对照保持。

## 实现与实际边界

- `chip_evolve/flow_recipe.py` 从已登记 ORFS 任务的实际输入准备固定镜像中的物理树，校验库、SDC、配置及辅助布线脚本，连同 `platforms/common` 共享映射文件复制；通过 EF 查询真实 Make 参数，再叠加原生控制器。
- `chip_evolve/professional.py` 在显式 source 模式使用新准备器，将 recipe 随结果交付；布局接力继承该物理来源。原 legacy 默认路径保留。
- `chip_evolve/cli.py` 增加 `run --capability flow --flow-recipe source`；其他专业不能误用此参数。
- `flow-agent/flow/run_sequential.sh` 在 source 模式从 Make 实测参数初始化原十维 CSV，替代旧的文本 grep 默认值。搜索域、随机扰动、约束、阶段屏障、候选继承、淘汰、CP0 与 TT 评分不变。
- 新增来源、辅助文件、数值起点及交接测试；既有不相关的用户工作保持。

所有工具探针、来源复制命令和物理实验经 EF。结果经共同测量、DF 导入及 SDK 查回；没有增加评分服务或修改公共 EF/DF/SDK 契约。

## 运行检查点

本机证据根：`var/business/a11-flow-source-20261015/`。

| 实验 | 用途 | 当前记录 |
|---|---|---|
| GCD/AES `source-recipe-qualification` | 内置综合来源的未调参物理复制控制 | 七项共同 PPA 与各自来源逐值相同；只证明物理准备，不证明原旋钮完整能力 |
| `yosys-full-source` | 第一份完整 Yosys 来源尝试 | GCD 因布线脚本未随任务提交而失败；保留证据。AES 未提交，控制部署命名冲突亦已保留 |
| `yosys-full-source-r2` | 辅助脚本作为 EF 输入提交的新完整来源 | GCD 已完成；AES 运行中，以各目录 `status.json` 为准 |
| GCD `yosys-source-qualification` | 首次复制完整 Yosys 来源 | 缺少 `platforms/common/lcu_kogge_stone.v`，综合失败；保留，不修改失败副本 |
| GCD/AES `yosys-source-qualification-r2` | 补齐共享映射文件后的来源资格 | 运行中；必须七项 PPA 与登记来源逐值相同 |
| AES `aes-yosys-native-2x3` | 原生两轮、每轮三候选 | 两设计来源资格通过后启动；未结束前不计为完整搜索成功 |

根回归初次为 219 passed；生产 Flow 环境回归 63 passed。Flow 源码 `.venv` 含旧 Toolkit wheel，原生测试中有一项缺 `eda_toolkits.context`；采用实际实验所用生产环境运行同一组测试全部通过。根 `dev.py` 的 Flow 测试命令另有原项目本地模块收集路径问题，本轮未改动该公共开发脚本。26 份保护文件均未改变。

## 尚待完成

来源资格、原旋钮实际消费核查、AES 正常搜索收尾、新候选的共同 PPA/约束/紧凑事实及 Query。仅有合格新输入时运行一条新 DPL 接力，并保留无 DPL 控制。没有合格新结果时继续保留 A9 合法 incumbent，不将来源变化收益算作专业协同收益。

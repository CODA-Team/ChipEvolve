# QoR Comparator 使用说明

## 1. 模型用途

QoR Comparator 用于比较一条 **baseline 完整物理设计轨迹** 与一条 **ongoing 部分物理设计轨迹**，预测 ongoing 相对 baseline 的最终 QoR 表现（最终指在统一cp_0下重测的结果）。

当前模型针对两个目标指标进行三分类预测：
- `setup_tns_ns`
  - `better`：ongoing 的最终 TNS 优于 baseline
  - `similar`：ongoing 与 baseline 基本相同
  - `worse`：ongoing 的最终 TNS 劣于 baseline
- `power_total_w`
  - `better`：ongoing 的最终总功耗低于 baseline
  - `similar`：ongoing 与 baseline 的总功耗变化在 5% 容忍范围内
  - `worse`：ongoing 的最终总功耗相对 baseline 恶化超过 5%

模型进一步根据两个目标指标的预测概率输出：
- `kill_score`：该 ongoing 应被提前终止的风险分数
- `promising_score`：该 ongoing 在功耗可接受的情况下改善 TNS 的潜力分数

当前代码包中的 `evaluate.py` 是离线测试与评估代码，不直接等同于最终在线推理接口，但其中的数据预处理、模型加载、前向推理、分数计算和决策逻辑可作为在线接口实现参考。

---

## 2. 文件结构

```text
predict_model_v2/
├── README.md
├── example_config.json
├── evaluate.py
├── best_model.pt
└── qor_comparator/
    ├── __init__.py
    ├── config.py
    ├── dataset.py
    └── model.py
```

其中：
- `best_model.pt`：训练好的模型权重
- `example_config.json`：当前模型的数据字段、检查点顺序和网络结构配置
- `qor_comparator/model.py`：模型结构及 `kill_score`、`promising_score` 计算逻辑
- `qor_comparator/dataset.py`：轨迹读取、检查点对齐、归一化和标签生成逻辑
- `evaluate.py`：离线测试脚本，可作为在线推理接口实现参考
---

## 3. 在线推理需要的输入

在线推理的最小语义输入为：
1. baseline 的完整原生 QoR 轨迹
2. ongoing 当前已完成部分的原生 QoR 轨迹
3. baseline 的原始时钟周期 `baseline_original_cp`
4. ongoing 的原始时钟周期 `ongoing_original_cp`
5. 两者统一评价时钟周期 `eval_cp0`

## 3.1 Baseline 轨迹

baseline 应提供完整的原生物理设计轨迹，当前模型配置的原生检查点顺序为：
```text
post_floorplan
post_global_placement
post_place_resize
post_detailed_placement
post_cts
post_global_route
final_report
```
baseline 须包含以上 7 个检查点，并严格使用相同名称，不需要 final_eval（最终在统一eval_cp0下的评估值）。

检查点文件如下【摘自 extract_trajectories_v2.py  110-118行】：
MAJOR_FILE_PATTERNS = [
    re.compile(r"^2_1_.*floorplan.*\.json$", re.IGNORECASE),
    re.compile(r"^3_3_.*place_gp.*\.json$", re.IGNORECASE),
    re.compile(r"^3_4_.*resized.*\.json$", re.IGNORECASE),
    re.compile(r"^3_5_.*place_dp.*\.json$", re.IGNORECASE),
    re.compile(r"^4_1_.*cts.*\.json$", re.IGNORECASE),
    re.compile(r"^5_1_.*grt.*\.json$", re.IGNORECASE),
    re.compile(r"^6_.*report.*\.json$", re.IGNORECASE),
]

## 3.2 Ongoing 轨迹

ongoing 应提供从流程起点开始的连续轨迹前缀，不能跳过中间阶段，例如：
```text
post_floorplan
post_global_placement
post_place_resize
```

当前配置要求：
- ongoing 至少包含 2 个原生检查点
- ongoing 的检查点必须是 baseline 检查点序列的前缀
- baseline 与 ongoing 的对应检查点名称和顺序必须一致
- ongoing 也无需 final_eval 行

有效示例：

```text
baseline:
post_floorplan
post_global_placement
post_place_resize
post_detailed_placement
post_cts
post_global_route
final_report

ongoing:
post_floorplan
post_global_placement
post_place_resize
```

---

# 4. 轨迹 CSV 格式

## 4.1 必需列

当前配置要求每条轨迹至少包含以下列：

```text
checkpoint
setup_tns_ns
setup_wns_ns
power_total_w
power_leakage_w
instance_area_um2
instance_count
```

其中：
- `checkpoint`：检查点名称
- 其余 6 列：模型输入 QoR 特征

列顺序不强制，但列名必须一致。

## 4.2 在线输入示例

### Baseline 轨迹示例

```csv
checkpoint,setup_tns_ns,setup_wns_ns,power_total_w,power_leakage_w,instance_area_um2,instance_count
post_floorplan,-120.5,-8.2,0.092,0.0031,81234.0,10342
post_global_placement,-88.4,-5.7,0.101,0.0032,82981.0,10510
post_place_resize,-61.7,-3.9,0.108,0.0034,84720.0,10784
post_detailed_placement,-48.2,-3.0,0.111,0.0035,85210.0,10830
post_cts,-35.9,-2.4,0.119,0.0038,87360.0,11105
post_global_route,-20.7,-1.6,0.126,0.0040,88942.0,11320
final_report,-12.3,-0.9,0.131,0.0041,89500.0,11402
```

### Ongoing 部分轨迹示例

```csv
checkpoint,setup_tns_ns,setup_wns_ns,power_total_w,power_leakage_w,instance_area_um2,instance_count
post_floorplan,-130.1,-8.9,0.094,0.0032,81820.0,10405
post_global_placement,-97.6,-6.4,0.104,0.0033,83610.0,10602
post_place_resize,-72.8,-4.6,0.112,0.0035,85440.0,10876
```

以上数值仅用于展示格式。

## 4.3 缺失值处理

当前配置启用了：

```json
"append_missing_mask": true,
"missing_value_fill": 0.0
```

因此单个检查点中的部分 QoR 指标可以缺失。预处理时会：

1. 为每个输入指标生成 observed/missing mask
2. 将缺失值标准化后填为 `0.0`
3. 将缺失 mask 拼接到模型输入特征中

但 baseline 的某一个输入指标不能在整条 baseline 轨迹中全部缺失，否则无法计算该指标的归一化均值和标准差，代码会报错。

---

# 5. 时钟周期输入

模型额外需要三个正数：

```text
baseline_original_cp
ongoing_original_cp
eval_cp0
```

dataset.py 中会自动计算两个 ratio 并传入 QoRComparator.forward() ：

```text
baseline_clock_ratio = baseline_original_cp / eval_cp0
ongoing_clock_ratio  = ongoing_original_cp / eval_cp0
```

要求：

- 三者必须是有限正数
- baseline 与 ongoing 可以具有不同的 `original_cp`
- baseline 与 ongoing 必须使用相同的 `eval_cp0`
- 所有时钟周期必须使用同一单位

---

# 6. 预处理要求

上层若不直接复用 `QoRPairDataset`，则必须严格复现以下处理过程。

## 6.1 检查点排序

按照配置中的固定顺序：

```text
post_floorplan
post_global_placement
post_place_resize
post_detailed_placement
post_cts
post_global_route
final_report
```

分配 checkpoint ID：

```text
post_floorplan            -> 0
post_global_placement     -> 1
post_place_resize         -> 2
post_detailed_placement   -> 3
post_cts                  -> 4
post_global_route         -> 5
final_report              -> 6
```

不能传入未配置的检查点名称，也不能出现重复检查点。

## 6.2 配对归一化

当前模型不使用全数据集统一统计量，而是对每一个 baseline-ongoing pair 独立归一化，处理步骤：

1. 使用 baseline 完整原生轨迹，逐输入指标计算均值和标准差
2. baseline 使用该组均值和标准差进行标准化
3. ongoing 使用同一组 baseline 均值和标准差进行标准化
4. 标准差下限由 `normalization_eps=1e-6` 控制


## 6.3 Progress

当前进度定义为：

```text
progress = ongoing_prefix_length / 7
```

并限制在 `[0, 1]`。

## 6.4 模型张量输入

模型前向输入为：

```python
model(
    baseline_features=...,
    baseline_checkpoint_ids=...,
    baseline_valid_mask=...,
    ongoing_features=...,
    ongoing_checkpoint_ids=...,
    ongoing_valid_mask=...,
    progress=...,
    baseline_clock_ratio=...,
    ongoing_clock_ratio=...,
)
```

典型形状：

```text
baseline_features:          [batch_size, baseline_length, input_dim]
ongoing_features:           [batch_size, ongoing_length, input_dim]
baseline_checkpoint_ids:    [batch_size, baseline_length]
ongoing_checkpoint_ids:     [batch_size, ongoing_length]
baseline_valid_mask:        [batch_size, baseline_length]
ongoing_valid_mask:         [batch_size, ongoing_length]
progress:                   [batch_size, 1]
baseline_clock_ratio:       [batch_size, 1]
ongoing_clock_ratio:        [batch_size, 1]
```

当前配置包含 6 个输入指标，并启用 missing mask，因此：

```text
input_dim = 6 × 2 = 12
```

---

# 7. 模型可提供的输出

## 7.1 每个 QoR 的三分类结果

模型输出：

```python
outputs["probabilities"]
```

形状：

```text
[batch_size, num_target_metrics, 3]
```

当前 `num_target_metrics = 2`，类别顺序固定为：

```text
0 = better
1 = similar
2 = worse
```

因此每个 pair 可得到：

```text
setup_tns_ns:
- p_better
- p_similar
- p_worse
- predicted_class

power_total_w:
- p_better
- p_similar
- p_worse
- predicted_class
```


## 7.2 Kill score

定义：

```text
p_power_worse = power_total_w 的 worse 概率
p_tns_worse   = setup_tns_ns 的 worse 概率

kill_score = 1 - (1 - p_power_worse) × (1 - p_tns_worse)

0 ≤ kill_score ≤ 1
```

解释：

- 越接近 1：模型越认为 ongoing 存在功耗恶化或 TNS 恶化风险
- 越接近 0：模型越认为 ongoing 不需要提前终止

当前默认 threshold 为：

```text
0.8
```

可采用：

```text
kill_score >= 0.8 -> kill
kill_score < 0.8  -> continue
```

阈值属于上层决策策略，可根据流程阶段和误杀代价调整。

## 7.3 Promising score

定义：

```text
p_power_feasible = 1 - p_power_worse
p_tns_better     = setup_tns_ns 的 better 概率

promising_score = p_power_feasible × p_tns_better

0 ≤ promising_score ≤ 1
```

解释：

- 越接近 1：模型越认为该 ongoing 在功耗可接受的情况下有机会改善 TNS
- 越接近 0：模型越不认为该 ongoing 具有保留价值

`promising_score` 适合作为辅助信息，不建议单独代替 `kill_score` 做硬决策。

---

# 8. 离线 evaluate.py 所需数据

`evaluate.py` 用于测试模型，因此除了模型在线推理所需输入外，还需要真实最终结果和数据集清单。

## 8.1 run_manifest.csv

必需列：

```text
run_id
trajectory_path
split
original_cp
eval_cp0
```

示例：

```csv
run_id,trajectory_path,split,platform,design,variant,original_cp,eval_cp0
asap7__aes__run_1,asap7/aes/run_1/trajectory.csv,test,asap7,aes,run_1,0.95,0.90
asap7__aes__run_2,asap7/aes/run_2/trajectory.csv,test,asap7,aes,run_2,1.00,0.90
```

## 8.2 pair_manifest.csv

必需列：

```text
baseline_run_id
ongoing_run_id
split
prefix_ratio
```

示例：

```csv
baseline_run_id,ongoing_run_id,split,prefix_ratio
asap7__aes__run_1,asap7__aes__run_2,test,0.5
```

pair 须满足：

- baseline 和 ongoing 不能是同一个 run
- 二者必须属于同一个 split
- 二者必须属于同一个 platform
- 二者必须属于同一个 design
- 二者的 `eval_cp0` 必须相同
- 二者的 `original_cp` 可以不同

## 8.3 离线 trajectory.csv 的 final_eval 行

离线评估使用的每个 `trajectory.csv` 必须恰好包含一行：
```text
checkpoint = final_eval
```

该行只用于生成真实标签和评估结果，不能送入 Transformer，且至少需要在 `final_eval` 行中提供：

```text
setup_tns_ns
power_total_w
```

示例：

```csv
checkpoint,setup_tns_ns,setup_wns_ns,power_total_w,power_leakage_w,instance_area_um2,instance_count
post_floorplan,-120.5,-8.2,0.092,0.0031,81234.0,10342
post_global_placement,-88.4,-5.7,0.101,0.0032,82981.0,10510
post_place_resize,-61.7,-3.9,0.108,0.0034,84720.0,10784
post_detailed_placement,-48.2,-3.0,0.111,0.0035,85210.0,10830
post_cts,-35.9,-2.4,0.119,0.0038,87360.0,11105
post_global_route,-20.7,-1.6,0.126,0.0040,88942.0,11320
final_report,-12.3,-0.9,0.131,0.0041,89500.0,11402
final_eval,-18.5,,0.134,,,
```

`final_eval`：

- 不计入轨迹长度
- 不参与 progress 计算
- 不参与归一化
- 不进入 Transformer
- 只作为最终真实 QoR 标签来源

---

# 9. 离线评估示例

## 9.1 Threshold 模式

```bash
python3 evaluate.py \
  --config example_config.json \
  --checkpoint best_model.pt \
  --split test \
  --prefix-ratio 0.5 \
  --kill-mode threshold \
  --kill-threshold 0.8 \
  --tns-significant-degradation 0.0 \
  --tns-metric setup_tns_ns \
  --power-metric power_total_w \
  --output-dir outputs/evaluation
```

预测决策：

```text
kill_score >= kill_threshold -> kill
```

离线真实 kill 定义：

```text
power 相对 baseline 恶化超过 5%
或
TNS 相对 baseline 的恶化超过 tns_significant_degradation
```

## 9.2 Ratio 模式

```bash
python3 evaluate.py \
  --config example_config.json \
  --checkpoint best_model.pt \
  --split test \
  --prefix-ratio 0.5 \
  --kill-mode ratio \
  --kill-ratio 0.10 \
  --tns-metric setup_tns_ns \
  --power-metric power_total_w \
  --output-dir outputs/evaluation
```

同一个 baseline 下的 ongoing 按以下顺序排序：

1. `kill_score` 从高到低
2. `kill_score` 相同时，`promising_score` 从低到高
3. 两者都相同时，保持原始顺序

Ratio 模式主要用于离线排名实验，不代表当前推荐的在线硬决策方式。

---

# 10. 注意事项

1. `final_eval` 只能用于离线标签和评估，不作为在线模型输入。当前的 dataset.py 适配于离线评估，要求轨迹中恰好有一行 final_eval，因此当前的 dataset.py 不可直接用于在线预测，在线预测代码需要复用或提取其预处理逻辑，但跳过 final_eval 和标签生成部分。
2. baseline 推荐使用完整 7 检查点轨迹。
3. ongoing 必须是从第一个检查点开始的连续前缀，当前至少 2 个检查点。
4. checkpoint 名称必须与配置完全一致。
5. baseline 和 ongoing 必须属于同一 platform、同一 design，并使用相同 `eval_cp0`。
6. `original_cp` 可以不同，但 CP 与 CP0 的单位必须一致。
7. `kill_score` 表示分类风险，不等同于真实 QoR 恶化幅度。
8. 在线接口建议同时返回分类概率、`kill_score` 和 `promising_score`，方便上层制定决策策略。（evaluate.py内置两种策略供参考）
9. 离线 evaluate.py ≠ 在线推理接口 ≠ QoRComparator 模型本体

---

# 11. 推荐在线调用流程

```text
读取 baseline 完整轨迹（dataset.py）
        ↓
读取 ongoing 当前轨迹前缀（dataset.py）
        ↓
校验检查点名称、顺序和前缀对齐（dataset.py）
        ↓
读取 baseline_original_cp、ongoing_original_cp、eval_cp0
        ↓
以 baseline 完整轨迹计算每个输入指标的均值和标准差，同时标准化 baseline 与 ongoing（dataset.py）
        ↓
构造 checkpoint IDs、valid masks、progress 和 clock ratios（dataset.py）
        ↓
加载 best_model.pt
        ↓
执行 QoRComparator.forward()
        ↓
得到每个 QoR 的 better/similar/worse 概率
        ↓
调用 QoRComparator.compute_kill_score()
        ↓
输出 kill_score、promising_score 和上层决策
```

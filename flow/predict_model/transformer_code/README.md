# Transformer-DRP

Transformer-DRP is a Transformer-based QoR comparator for early doomed-run prediction in physical design. It compares a completed **baseline** trajectory with a partially observed **ongoing** trajectory and predicts whether the ongoing run will eventually be **Better**, **Similar**, or **Worse** than the baseline in terms of setup TNS and total power.

This repository contains the data-processing, model-training, and evaluation code for the Transformer-DRP component used in the accompanying paper.

## Scope

The repository focuses on Transformer-DRP only. An integration-specific online inference script is not included. In the complete system, the trained comparator is called by the upper-level physical-design optimization framework. The reusable model definition and pretrained checkpoint are provided in this repository.

## Repository Structure

```text
.
├── checkpoints/
│   └── best_model.pt
├── configs/
│   └── transformer_drp.json
├── data_processing/
│   ├── extract_trajectories.py
│   ├── dedup_trajectories.py
│   ├── build_run_manifest.py
│   └── build_pairs.py
├── qor_comparator/
│   ├── __init__.py
│   ├── config.py
│   ├── dataset.py
│   └── model.py
├── scripts/
│   ├── train.py
│   └── evaluate.py
├── README.md
├── requirements.txt
└── LICENSE
```

## Method Overview

Each physical-design run is represented by a sequence of QoR checkpoints. The model receives:

- the complete native trajectory of a baseline run;
- a prefix of the native trajectory of an ongoing run;
- the observed progress ratio;
- the baseline and ongoing clock ratios with respect to a common evaluation clock period, `eval_cp0`.

The baseline and ongoing trajectories are encoded by the **same shared Transformer encoder**. Let their encoded representations be \(h_B\) and \(h_C\). The comparator forms the fused representation

```text
[h_B, h_C, h_C - h_B, h_C * h_B, progress,
 baseline_clock_ratio, ongoing_clock_ratio]
```

and feeds it to independent three-class classification heads for:

- setup TNS;
- total power.

The class order is fixed as:

```text
0 = Better
1 = Similar
2 = Worse
```

The final labels are generated from `final_eval`, which contains the QoR values obtained by re-evaluating both runs under the same `eval_cp0`. The `final_eval` row is used only for label generation and evaluation; it is never passed to the Transformer as an input checkpoint.

### Pair-wise normalization

For every baseline/ongoing pair, the complete native baseline trajectory is used to compute the mean and standard deviation of each input QoR. Both trajectories are normalized with the same baseline statistics. Missing-value masks can optionally be appended to the normalized features.

### False-worse penalty

In addition to the standard classification loss, training applies an additional penalty when a sample whose true label is Better/Similar receives excessive probability on the Worse class. In the released configuration, the penalty weights are:

```text
setup_tns_ns : 0.2
power_total_w: 0.3
```

### Constraint-aware killing score

For the two target metrics, the model computes

```text
kill_score = 1 - (1 - P_power,worse) * (1 - P_tns,worse)
```

and

```text
promising_score = (1 - P_power,worse) * P_tns,better
```

The default power tolerance in `configs/transformer_drp.json` is 5% relative degradation with respect to the baseline under the common evaluation clock period.

## Checkpoints and Input Metrics

The default configuration uses the following seven native physical-design checkpoints:

```text
post_floorplan
post_global_placement
post_place_resize
post_detailed_placement
post_cts
post_global_route
final_report
```

The six input QoRs are:

```text
setup_tns_ns
setup_wns_ns
power_total_w
power_leakage_w
instance_area_um2
instance_count
```

With the missing-value mask enabled, the raw model input dimension is 12.

## Installation

Python 3.10 or later is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For GPU training, install a PyTorch build compatible with the local CUDA environment if necessary.

## Data Preparation

The repository does not include raw ORFS run directories. The scripts under `data_processing/` convert ORFS outputs into the manifests consumed by the model.

A typical pipeline is:

```text
ORFS logs/reports
      |
      v
extract_trajectories.py
      |
      v
trajectory.csv + metadata.json
      |
      v
(optional) dedup_trajectories.py
      |
      v
build_run_manifest.py
      |
      v
run_manifest.csv
      |
      v
build_pairs.py
      |
      v
pair_manifest.csv
```

### 1. Extract trajectories

For an archived `logs_dump` directory:

```bash
python data_processing/extract_trajectories.py \
  --logs-dump-root /path/to/result_dump_1/logs_dump \
  --platform asap7 \
  --design aes \
  --output-dir /path/to/qor_dataset \
  --mode major
```

Each extracted run contains a `trajectory.csv`. A valid trajectory must contain the configured native checkpoints and exactly one `final_eval` row.

### 2. Optional trajectory deduplication

```bash
python data_processing/dedup_trajectories.py \
  /path/to/qor_dataset_1 \
  /path/to/qor_dataset_2 \
  --report /path/to/duplicate_trajectory_report.csv \
  --action check
```

Use `--action move` or `--action delete` only after inspecting the report.

### 3. Build the run manifest

```bash
python data_processing/build_run_manifest.py \
  --roots /path/to/qor_dataset_1 /path/to/qor_dataset_2 \
  --output data/run_manifest.csv \
  --relative-paths \
  --overwrite
```

The generated manifest records, among other fields:

```text
run_id
trajectory_path
platform
design
variant
split
original_cp
eval_cp0
final_eval_tns
final_eval_power
```

Train/validation/test splitting is performed at run level.

### 4. Build baseline/ongoing pairs

```bash
python data_processing/build_pairs.py \
  --run-manifest data/run_manifest.csv \
  --output data/pair_manifest.csv \
  --shuffle-output
```

Pairs are generated only between runs with the same:

- platform;
- design;
- data split;
- `eval_cp0`.

The baseline and ongoing runs are allowed to have different original clock periods. Their clock ratios are derived as

```text
original_cp / eval_cp0
```

and are provided to the model as scalar features.

## Configuration

The released configuration is:

```text
configs/transformer_drp.json
```

Paths in the JSON configuration are resolved relative to the configuration file itself. The default paths therefore expect:

```text
data/run_manifest.csv
data/pair_manifest.csv
```

relative to the repository root.

Important configuration fields include:

- `input_metrics`: native QoRs used as model inputs;
- `checkpoint_order`: expected physical-design checkpoint order;
- `target_metrics`: target directions, tolerances, loss weights, and false-worse penalties;
- `train_prefix_ratios`: candidate ongoing-prefix ratios sampled during training;
- `eval_prefix_ratio`: default prefix ratio used for evaluation;
- Transformer dimensions and dropout parameters;
- training hyperparameters and kill threshold.

## Training

Run training from the repository root:

```bash
python -m scripts.train \
  --config configs/transformer_drp.json
```

The training script:

- loads baseline/ongoing pairs from the manifests;
- samples ongoing prefixes according to the configured training ratios;
- optimizes the multi-task classification loss with false-worse penalties;
- evaluates on the validation split;
- saves the checkpoint with the lowest validation loss as `best_model.pt` in the configured output directory.

A pretrained checkpoint corresponding to the released model is included at:

```text
checkpoints/best_model.pt
```

## Evaluation

### Threshold mode

Threshold mode kills a candidate when `kill_score >= kill_threshold`.

```bash
python -m scripts.evaluate \
  --config configs/transformer_drp.json \
  --checkpoint checkpoints/best_model.pt \
  --split test \
  --kill-mode threshold \
  --kill-threshold 0.8 \
  --tns-significant-degradation 0.0 \
  --tns-metric setup_tns_ns \
  --power-metric power_total_w
```

If `--kill-threshold` is omitted, the value from `config.training.kill_threshold` is used.

The power violation threshold is read directly from the selected power metric's `relative_tolerance` in the configuration.

### Ratio mode

Ratio mode ranks the ongoing candidates associated with each baseline and kills a fixed fraction of each group.

```bash
python -m scripts.evaluate \
  --config configs/transformer_drp.json \
  --checkpoint checkpoints/best_model.pt \
  --split test \
  --kill-mode ratio \
  --kill-ratio 0.10 \
  --tns-metric setup_tns_ns \
  --power-metric power_total_w
```

The evaluator reports classification statistics, confusion matrices, continuous QoR degradation information, and killing-related metrics. The reported `average_cross_entropy` is the evaluation cross-entropy only; it does not include the false-worse training penalty.

## Pretrained Checkpoint

The released `checkpoints/best_model.pt` contains:

- the model state dictionary;
- the optimizer state dictionary;
- target metric names;
- validation statistics;
- the false-worse weights used during training.

The provided checkpoint uses:

```text
setup_tns_ns false-worse weight : 0.2
power_total_w false-worse weight: 0.3
```

## Notes on Reproducibility

- `final_eval` is excluded from the Transformer input to avoid target leakage.
- Baseline and ongoing runs in a pair must share the same `eval_cp0`.
- Baseline and ongoing native clock periods may differ.
- Relative file paths in the manifests are recommended for portability.
- Exact runtime and GPU memory usage depend on the dataset size, pair count, and local PyTorch/CUDA environment.

## License

This repository is released under the MIT License. See [LICENSE](LICENSE).

Third-party tools and libraries, including OpenROAD/OpenROAD-flow-scripts, are not redistributed by this repository and remain subject to their own licenses.

## Citation

If you use this code in academic work, please cite the corresponding paper. Full citation information can be added here after publication.

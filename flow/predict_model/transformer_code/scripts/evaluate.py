#!/usr/bin/env python3
"""
在 train/val/test split 上评估训练好的 QoR Comparator。

支持两种 kill 决策模式：
1. threshold: kill_score >= kill_threshold 时 kill。
python -m scripts.evaluate \
  --config configs/transformer_drp.json \
  --checkpoint checkpoints/best_model.pt \
  --split test \
  --kill-mode threshold \
  --kill-threshold 0.8 \
  --tns-significant-degradation 0.0 \
  --tns-metric setup_tns_ns \
  --power-metric power_total_w
2. ratio: 在每个 baseline 对应的 ongoing 候选集合内，按 kill_score
   从高到低选择指定比例;kill_score 相同时,promising_score 更低者
   优先被 kill。
python -m scripts.evaluate \
  --config configs/transformer_drp.json \
  --checkpoint checkpoints/best_model.pt \
  --split test \
  --kill-mode ratio \
  --kill-ratio 0.10 \
  --tns-metric setup_tns_ns \
  --power-metric power_total_w


当前约束优化目标：
- power 相比 baseline 的恶化不超过 target_metrics 中设定的容忍度；
- 在功耗约束可接受的前提下优化 TNS。

"""

from __future__ import annotations

import argparse
import csv
import inspect
import json
import math
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from qor_comparator.config import ExperimentConfig
from qor_comparator.dataset import (
    BETTER,
    CLASS_NAMES,
    IGNORE_LABEL,
    SIMILAR,
    WORSE,
    QoRPairDataset,
    collate_qor_pairs,
)
from qor_comparator.model import QoRComparator



def choose_device(device_config: str) -> torch.device:
    if device_config == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(device_config)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("No usable CUDA")
    return device


def move_batch_to_device(
    batch: Mapping[str, Any],
    device: torch.device,
) -> Dict[str, Any]:
    return {
        key: value.to(device) if torch.is_tensor(value) else value
        for key, value in batch.items()
    }


def build_loader(
    dataset: QoRPairDataset,
    batch_size: int,
    num_workers: int,
) -> DataLoader:
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        collate_fn=collate_qor_pairs,
        pin_memory=torch.cuda.is_available(),
    )


def forward_model(
    model: QoRComparator,
    batch: Mapping[str, Any],
) -> Dict[str, torch.Tensor]:
    kwargs: Dict[str, torch.Tensor] = {
        "baseline_features": batch["baseline_features"],
        "baseline_checkpoint_ids": batch["baseline_checkpoint_ids"],
        "baseline_valid_mask": batch["baseline_valid_mask"],
        "ongoing_features": batch["ongoing_features"],
        "ongoing_checkpoint_ids": batch["ongoing_checkpoint_ids"],
        "ongoing_valid_mask": batch["ongoing_valid_mask"],
        "progress": batch["progress"],
    }

    forward_parameters = inspect.signature(model.forward).parameters
    if (
        "baseline_clock_ratio" in batch
        and "baseline_clock_ratio" in forward_parameters
    ):
        kwargs["baseline_clock_ratio"] = batch["baseline_clock_ratio"]
    if (
        "ongoing_clock_ratio" in batch
        and "ongoing_clock_ratio" in forward_parameters
    ):
        kwargs["ongoing_clock_ratio"] = batch["ongoing_clock_ratio"]

    return model(**kwargs)


def compute_multitask_loss(
    logits: torch.Tensor,
    labels: torch.Tensor,
    loss_weights: torch.Tensor,
) -> torch.Tensor:
    total = logits.new_tensor(0.0)
    valid_weight_sum = logits.new_tensor(0.0)

    for metric_index in range(logits.shape[1]):
        metric_labels = labels[:, metric_index]
        valid = metric_labels != IGNORE_LABEL
        if not torch.any(valid):
            continue

        metric_loss = nn.functional.cross_entropy(
            logits[valid, metric_index, :],
            metric_labels[valid],
        )
        weight = loss_weights[metric_index]
        total = total + weight * metric_loss
        valid_weight_sum = valid_weight_sum + weight

    if valid_weight_sum.item() <= 0:
        raise RuntimeError("当前 batch 的所有目标标签均缺失")
    return total / valid_weight_sum


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else float("nan")


def multiclass_metrics(confusion: np.ndarray) -> Dict[str, Any]:
    per_class: Dict[str, Any] = {}
    f1_values: List[float] = []
    weighted_f1_sum = 0.0
    support_sum = 0

    for class_index, class_name in enumerate(CLASS_NAMES):
        tp = int(confusion[class_index, class_index])
        fp = int(confusion[:, class_index].sum() - tp)
        fn = int(confusion[class_index, :].sum() - tp)
        support = int(confusion[class_index, :].sum())

        precision = safe_divide(tp, tp + fp)
        recall = safe_divide(tp, tp + fn)

        if (
            math.isfinite(precision)
            and math.isfinite(recall)
            and precision + recall > 0
        ):
            f1 = 2.0 * precision * recall / (precision + recall)
        elif support == 0:
            f1 = float("nan")
        else:
            f1 = 0.0

        per_class[class_name] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }

        if math.isfinite(f1):
            f1_values.append(f1)
            weighted_f1_sum += f1 * support
            support_sum += support

    return {
        "per_class": per_class,
        "macro_f1": float(np.mean(f1_values)) if f1_values else float("nan"),
        "weighted_f1": (
            weighted_f1_sum / support_sum if support_sum > 0 else float("nan")
        ),
    }


def binary_metrics(confusion: np.ndarray) -> Dict[str, Any]:
    tn = int(confusion[0, 0])
    fp = int(confusion[0, 1])
    fn = int(confusion[1, 0])
    tp = int(confusion[1, 1])

    accuracy = safe_divide(tp + tn, int(confusion.sum()))
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)

    if (
        math.isfinite(precision)
        and math.isfinite(recall)
        and precision + recall > 0
    ):
        f1 = 2.0 * precision * recall / (precision + recall)
    elif tp + fn == 0:
        f1 = float("nan")
    else:
        f1 = 0.0

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": confusion.tolist(),
        "class_order": ["continue", "kill"],
        "true_continue_count": int(confusion[0, :].sum()),
        "true_kill_count": int(confusion[1, :].sum()),
        "predicted_continue_count": int(confusion[:, 0].sum()),
        "predicted_kill_count": int(confusion[:, 1].sum()),
        "false_kill_count": fp,
        "missed_kill_count": fn,
    }


def resolve_metric_index(
    metric_names: Sequence[str],
    requested_name: Optional[str],
    kind: str,
) -> int:
    if requested_name is not None:
        try:
            return list(metric_names).index(requested_name)
        except ValueError as exc:
            raise ValueError(
                f"--{kind}-metric={requested_name!r} 不在 target_metrics 中；"
                f"可选值为 {list(metric_names)}"
            ) from exc

    scored: List[Tuple[int, int, str]] = []
    for index, name in enumerate(metric_names):
        lowered = name.lower()

        if kind == "tns":
            if "tns" not in lowered:
                continue
            score = 10
            if "setup" in lowered:
                score += 3
            if "eval" in lowered or "final" in lowered:
                score += 2
        elif kind == "power":
            if "power" not in lowered:
                continue
            score = 10
            if "total" in lowered:
                score += 3
            if "eval" in lowered or "final" in lowered:
                score += 2
        else:
            raise ValueError(f"未知指标类型: {kind}")

        scored.append((score, index, name))

    if not scored:
        raise ValueError(
            f"无法从 target_metrics 自动识别 {kind}；"
            f"当前目标为 {list(metric_names)}"
        )

    scored.sort(reverse=True)
    best_score = scored[0][0]
    best = [item for item in scored if item[0] == best_score]
    if len(best) != 1:
        raise ValueError(
            f"自动识别 {kind} 指标存在歧义：{[item[2] for item in best]}"
        )
    return best[0][1]


def score_statistics(values: np.ndarray) -> Dict[str, float]:
    if values.size == 0:
        return {
            "count": 0,
            "mean": float("nan"),
            "std": float("nan"),
            "min": float("nan"),
            "max": float("nan"),
        }
    return {
        "count": int(values.size),
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def resolve_split_name(config: ExperimentConfig, requested: str) -> str:
    aliases = {
        "train": config.data.train_split_name,
        "val": config.data.val_split_name,
        "test": config.data.test_split_name,
    }
    return aliases.get(requested, requested)


def json_ready(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    return value


def add_optional_batch_metadata(
    row: Dict[str, Any],
    raw_batch: Mapping[str, Any],
    row_index: int,
) -> None:
    for key in (
        "baseline_original_cp",
        "ongoing_original_cp",
        "eval_cp0",
    ):
        if key not in raw_batch:
            continue

        value = raw_batch[key]
        if torch.is_tensor(value):
            item = value[row_index]
            row[key] = float(item.reshape(-1)[0].item())
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            row[key] = value[row_index]
        else:
            row[key] = value


def compute_continuous_truth(
    baseline_final_tns: np.ndarray,
    ongoing_final_tns: np.ndarray,
    baseline_final_power: np.ndarray,
    ongoing_final_power: np.ndarray,
    power_degradation_limit: float,
) -> Dict[str, np.ndarray]:
    finite = (
        np.isfinite(baseline_final_tns)
        & np.isfinite(ongoing_final_tns)
        & np.isfinite(baseline_final_power)
        & np.isfinite(ongoing_final_power)
        & (baseline_final_power > 0.0)
    )

    # TNS 越高、越接近 0 越好；正数表示 ongoing 更差。
    tns_degradation = baseline_final_tns - ongoing_final_tns

    power_degradation_ratio = np.full(
        baseline_final_power.shape,
        np.nan,
        dtype=np.float64,
    )
    power_degradation_ratio[finite] = (
        ongoing_final_power[finite] / baseline_final_power[finite] - 1.0
    )

    power_violation = power_degradation_ratio > power_degradation_limit
    power_violation_amount = (
        power_degradation_ratio - power_degradation_limit
    )

    return {
        "valid": finite,
        "tns_degradation": tns_degradation,
        "power_degradation_ratio": power_degradation_ratio,
        "power_violation": power_violation,
        "power_violation_amount": power_violation_amount,
    }


def apply_threshold_mode(
    *,
    kill_scores: np.ndarray,
    truth: Mapping[str, np.ndarray],
    kill_threshold: float,
    tns_significant_degradation: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    predicted_kill = kill_scores >= kill_threshold
    valid = truth["valid"]

    # 两个条件任一满足即为真实 kill。
    true_kill = (
        (
            truth["power_violation"]
            | (truth["tns_degradation"] > tns_significant_degradation)
        )
        & valid
    )
    return predicted_kill, true_kill, valid


def apply_ratio_mode(
    *,
    kill_scores: np.ndarray,
    promising_scores: np.ndarray,
    baseline_run_ids: Sequence[str],
    truth: Mapping[str, np.ndarray],
    kill_ratio: float,
) -> Tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    List[int],
    List[int],
    List[Dict[str, Any]],
]:
    groups: Dict[str, List[int]] = defaultdict(list)
    for index, baseline_run_id in enumerate(baseline_run_ids):
        groups[str(baseline_run_id)].append(index)

    sample_count = len(kill_scores)
    predicted_kill = np.zeros(sample_count, dtype=bool)
    true_kill = np.zeros(sample_count, dtype=bool)
    predicted_rank = np.zeros(sample_count, dtype=np.int64)
    true_rank = np.zeros(sample_count, dtype=np.int64)
    group_sizes = [0] * sample_count
    group_kill_counts = [0] * sample_count
    group_rows: List[Dict[str, Any]] = []

    for baseline_run_id, indices in groups.items():
        invalid = [index for index in indices if not bool(truth["valid"][index])]
        if invalid:
            raise ValueError(
                "ratio 模式要求每个 pair 都有有效的连续 final TNS/power；"
                f"baseline={baseline_run_id} 存在 {len(invalid)} 条无效记录"
            )

        group_size = len(indices)
        kill_count = min(
            group_size,
            max(1, int(math.ceil(group_size * kill_ratio))),
        )

        # 预测排序：
        # 1. kill_score 越高，越优先 kill；
        # 2. kill_score 相同时，promising_score 越低，越优先 kill；
        # 3. 两者都相同时，使用原始顺序稳定打破平局。
        def predicted_sort_key(index: int) -> Tuple[float, float, int]:
            kill_score = float(kill_scores[index])
            promising_score = float(promising_scores[index])

            # 非有限值放在对应排序的最后，避免 NaN 破坏排序稳定性。
            kill_key = -kill_score if math.isfinite(kill_score) else math.inf
            promising_key = (
                promising_score
                if math.isfinite(promising_score)
                else math.inf
            )
            return kill_key, promising_key, index

        predicted_order = sorted(
            indices,
            key=predicted_sort_key,
        )

        # 真实排序遵循：功耗约束优先，随后比较违规程度和 TNS 恶化。
        true_order = sorted(
            indices,
            key=lambda index: (
                0 if bool(truth["power_violation"][index]) else 1,
                -max(float(truth["power_violation_amount"][index]), 0.0),
                -float(truth["tns_degradation"][index]),
                -float(truth["power_degradation_ratio"][index]),
                index,
            ),
        )

        for rank, index in enumerate(predicted_order, start=1):
            predicted_rank[index] = rank
        for rank, index in enumerate(true_order, start=1):
            true_rank[index] = rank

        predicted_selected = set(predicted_order[:kill_count])
        true_selected = set(true_order[:kill_count])

        for index in predicted_selected:
            predicted_kill[index] = True
        for index in true_selected:
            true_kill[index] = True

        overlap = len(predicted_selected & true_selected)
        precision_at_k = safe_divide(overlap, kill_count)
        recall_at_k = safe_divide(overlap, kill_count)

        for index in indices:
            group_sizes[index] = group_size
            group_kill_counts[index] = kill_count

        group_rows.append(
            {
                "baseline_run_id": baseline_run_id,
                "group_size": group_size,
                "kill_count": kill_count,
                "top_k_overlap": overlap,
                "precision_at_k": precision_at_k,
                "recall_at_k": recall_at_k,
            }
        )

    return (
        predicted_kill,
        true_kill,
        predicted_rank,
        true_rank,
        group_sizes,
        group_kill_counts,
        group_rows,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="评估训练好的 Transformer QoR 比较器"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--split", default="test")
    parser.add_argument("--prefix-ratio", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)

    parser.add_argument(
        "--kill-mode",
        choices=["threshold", "ratio"],
        default="threshold",
    )
    parser.add_argument(
        "--kill-threshold",
        type=float,
        default=None,
        help=(
            "threshold 模式下预测 kill_score 的阈值；"
            "默认使用 config.training.kill_threshold"
        ),
    )
    parser.add_argument(
        "--tns-significant-degradation",
        type=float,
        default=0.0,
        help=(
            "threshold 模式下真实标签使用的 TNS 显著恶化绝对阈值；"
            "单位与 final TNS 相同，默认 0"
        ),
    )
    parser.add_argument(
        "--kill-ratio",
        type=float,
        default=0.10,
        help="ratio 模式下每个 baseline 组 kill 的比例",
    )
    parser.add_argument("--tns-metric", default=None)
    parser.add_argument("--power-metric", default=None)
    args = parser.parse_args()

    if args.kill_threshold is not None and not (
        0.0 <= args.kill_threshold <= 1.0
    ):
        raise ValueError("--kill-threshold 必须位于 [0, 1]")
    if args.tns_significant_degradation < 0.0:
        raise ValueError("--tns-significant-degradation 不能为负")
    if not (0.0 < args.kill_ratio <= 1.0):
        raise ValueError("--kill-ratio 必须位于 (0, 1]")

    config = ExperimentConfig.from_json(args.config)

    if args.prefix_ratio is not None:
        if not (0.0 < args.prefix_ratio <= 1.0):
            raise ValueError("--prefix-ratio 必须位于 (0, 1]")
        config = replace(
            config,
            data=replace(
                config.data,
                eval_prefix_ratio=float(args.prefix_ratio),
            ),
        )

    split_name = resolve_split_name(config, args.split)
    checkpoint_path = (
        args.checkpoint
        if args.checkpoint is not None
        else config.training.output_dir / "best_model.pt"
    )
    output_dir = (
        args.output_dir
        if args.output_dir is not None
        else config.training.output_dir / "evaluation"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    if not checkpoint_path.exists():
        raise FileNotFoundError(f"模型检查点不存在: {checkpoint_path}")

    kill_threshold = (
        float(args.kill_threshold)
        if args.kill_threshold is not None
        else float(config.training.kill_threshold)
    )
    if not (0.0 <= kill_threshold <= 1.0):
        raise ValueError("最终 kill_threshold 必须位于 [0, 1]")

    device = choose_device(config.training.device)
    dataset = QoRPairDataset(
        config.data,
        split=split_name,
        training=False,
        seed=config.training.seed,
    )
    loader = build_loader(
        dataset,
        args.batch_size or config.training.batch_size,
        config.training.num_workers,
    )

    metric_names = [spec.name for spec in config.data.target_metrics]
    tns_metric_index = resolve_metric_index(
        metric_names,
        args.tns_metric,
        kind="tns",
    )
    power_metric_index = resolve_metric_index(
        metric_names,
        args.power_metric,
        kind="power",
    )
    if tns_metric_index == power_metric_index:
        raise ValueError("TNS 与 power 不能是同一个目标")

    tns_metric_name = metric_names[tns_metric_index]
    power_metric_name = metric_names[power_metric_index]
    power_metric_spec = config.data.target_metrics[power_metric_index]
    power_degradation_limit = float(power_metric_spec.relative_tolerance)
    if power_degradation_limit < 0.0:
        raise ValueError(
            "power metric 的 relative_tolerance 不能为负"
        )

    model = QoRComparator(
        input_dim=dataset.raw_feature_dim,
        num_checkpoints=len(config.data.checkpoint_order),
        target_metric_names=metric_names,
        config=config.model,
    ).to(device)

    checkpoint = torch.load(
        checkpoint_path,
        map_location=device,
        weights_only=False,
    )
    saved_metric_names = checkpoint.get("target_metric_names")
    if saved_metric_names is not None and list(saved_metric_names) != metric_names:
        raise ValueError(
            "checkpoint 与 config 的目标 QoR 不一致："
            f"\ncheckpoint={saved_metric_names}\nconfig={metric_names}"
        )

    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    loss_weights = torch.tensor(
        [spec.loss_weight for spec in config.data.target_metrics],
        dtype=torch.float32,
        device=device,
    )

    num_metrics = len(metric_names)
    confusion = np.zeros((num_metrics, 3, 3), dtype=np.int64)
    total_loss = 0.0
    total_samples = 0

    prediction_rows: List[Dict[str, Any]] = []
    baseline_run_ids: List[str] = []
    predicted_kill_scores: List[float] = []
    predicted_promising_scores: List[float] = []
    baseline_final_tns_values: List[float] = []
    ongoing_final_tns_values: List[float] = []
    baseline_final_power_values: List[float] = []
    ongoing_final_power_values: List[float] = []

    with torch.no_grad():
        for raw_batch in loader:
            batch = move_batch_to_device(raw_batch, device)
            outputs = forward_model(model, batch)
            logits = outputs["logits"]
            probabilities = outputs["probabilities"]
            labels = batch["labels"]

            loss = compute_multitask_loss(logits, labels, loss_weights)
            batch_size = labels.shape[0]
            total_loss += float(loss.cpu()) * batch_size
            total_samples += batch_size

            predictions = logits.argmax(dim=-1)
            for metric_index in range(num_metrics):
                valid = labels[:, metric_index] != IGNORE_LABEL
                true_values = labels[valid, metric_index].cpu().tolist()
                pred_values = predictions[valid, metric_index].cpu().tolist()
                for true_value, pred_value in zip(true_values, pred_values):
                    confusion[
                        metric_index,
                        int(true_value),
                        int(pred_value),
                    ] += 1

            score_outputs = model.compute_kill_score(
                probabilities,
                tns_metric_index=tns_metric_index,
                power_metric_index=power_metric_index,
            )

            for row_index in range(batch_size):
                baseline_run_id = raw_batch["baseline_run_id"][row_index]
                ongoing_run_id = raw_batch["ongoing_run_id"][row_index]

                baseline_final_tns = float(
                    raw_batch["baseline_final_tns"][row_index].item()
                )
                ongoing_final_tns = float(
                    raw_batch["ongoing_final_tns"][row_index].item()
                )
                baseline_final_power = float(
                    raw_batch["baseline_final_power"][row_index].item()
                )
                ongoing_final_power = float(
                    raw_batch["ongoing_final_power"][row_index].item()
                )

                baseline_run_ids.append(str(baseline_run_id))
                predicted_kill_scores.append(
                    float(score_outputs["kill_score"][row_index].cpu())
                )
                predicted_promising_scores.append(
                    float(score_outputs["promising_score"][row_index].cpu())
                )
                baseline_final_tns_values.append(baseline_final_tns)
                ongoing_final_tns_values.append(ongoing_final_tns)
                baseline_final_power_values.append(baseline_final_power)
                ongoing_final_power_values.append(ongoing_final_power)

                row: Dict[str, Any] = {
                    "baseline_run_id": baseline_run_id,
                    "ongoing_run_id": ongoing_run_id,
                    "prefix_length": int(raw_batch["prefix_length"][row_index]),
                    "progress": float(raw_batch["progress"][row_index].item()),
                    "baseline_final_tns": baseline_final_tns,
                    "ongoing_final_tns": ongoing_final_tns,
                    "baseline_final_power": baseline_final_power,
                    "ongoing_final_power": ongoing_final_power,
                    "predicted_kill_score": predicted_kill_scores[-1],
                    "predicted_promising_score": predicted_promising_scores[-1],
                }

                add_optional_batch_metadata(row, raw_batch, row_index)

                for metric_index, metric_name in enumerate(metric_names):
                    true_label = int(labels[row_index, metric_index].cpu())
                    pred_label = int(predictions[row_index, metric_index].cpu())
                    probs = probabilities[row_index, metric_index].cpu().tolist()

                    row[f"{metric_name}__true"] = (
                        CLASS_NAMES[true_label]
                        if true_label != IGNORE_LABEL
                        else "missing"
                    )
                    row[f"{metric_name}__pred"] = CLASS_NAMES[pred_label]
                    row[f"{metric_name}__p_better"] = float(probs[BETTER])
                    row[f"{metric_name}__p_similar"] = float(probs[SIMILAR])
                    row[f"{metric_name}__p_worse"] = float(probs[WORSE])

                prediction_rows.append(row)

    predicted_kill_array = np.asarray(predicted_kill_scores, dtype=np.float64)
    predicted_promising_array = np.asarray(
        predicted_promising_scores,
        dtype=np.float64,
    )

    truth = compute_continuous_truth(
        np.asarray(baseline_final_tns_values, dtype=np.float64),
        np.asarray(ongoing_final_tns_values, dtype=np.float64),
        np.asarray(baseline_final_power_values, dtype=np.float64),
        np.asarray(ongoing_final_power_values, dtype=np.float64),
        power_degradation_limit=power_degradation_limit,
    )

    for index, row in enumerate(prediction_rows):
        row["true_tns_degradation"] = float(truth["tns_degradation"][index])
        row["true_power_degradation_ratio"] = float(
            truth["power_degradation_ratio"][index]
        )
        row["true_power_violation"] = bool(truth["power_violation"][index])

    group_rows: List[Dict[str, Any]] = []

    if args.kill_mode == "threshold":
        predicted_kill, true_kill, valid_decision = apply_threshold_mode(
            kill_scores=predicted_kill_array,
            truth=truth,
            kill_threshold=kill_threshold,
            tns_significant_degradation=float(
                args.tns_significant_degradation
            ),
        )

        for index, row in enumerate(prediction_rows):
            row.update(
                {
                    "kill_threshold": kill_threshold,
                    "tns_significant_degradation": float(
                        args.tns_significant_degradation
                    ),
                    "true_decision": (
                        "kill" if true_kill[index] else "continue"
                    ) if valid_decision[index] else None,
                    "predicted_decision": (
                        "kill" if predicted_kill[index] else "continue"
                    ),
                }
            )

        mode_details: Dict[str, Any] = {
            "mode": "threshold",
            "kill_threshold": kill_threshold,
            "tns_significant_degradation": float(
                args.tns_significant_degradation
            ),
            "power_degradation_limit": power_degradation_limit,
            "ground_truth_definition": (
                f"power_degradation_ratio > {power_degradation_limit:g} OR "
                "tns_degradation > tns_significant_degradation"
            ),
            "rank_output": False,
        }

    else:
        (
            predicted_kill,
            true_kill,
            predicted_rank,
            true_rank,
            group_sizes,
            group_kill_counts,
            group_rows,
        ) = apply_ratio_mode(
            kill_scores=predicted_kill_array,
            promising_scores=predicted_promising_array,
            baseline_run_ids=baseline_run_ids,
            truth=truth,
            kill_ratio=float(args.kill_ratio),
        )
        valid_decision = truth["valid"]

        for index, row in enumerate(prediction_rows):
            row.update(
                {
                    "predicted_kill_rank": int(predicted_rank[index]),
                    "true_kill_rank": int(true_rank[index]),
                    "selection_group_size": int(group_sizes[index]),
                    "selection_group_kill_count": int(group_kill_counts[index]),
                    "true_decision": (
                        "kill" if true_kill[index] else "continue"
                    ),
                    "predicted_decision": (
                        "kill" if predicted_kill[index] else "continue"
                    ),
                }
            )

        precision_values = np.asarray(
            [row["precision_at_k"] for row in group_rows],
            dtype=np.float64,
        )
        total_overlap = int(
            sum(row["top_k_overlap"] for row in group_rows)
        )

        mode_details = {
            "mode": "ratio",
            "kill_ratio": float(args.kill_ratio),
            "scope": "baseline",
            "ratio_rounding": (
                "ceil，且每个非空 baseline 组至少 kill 1 条"
            ),
            "predicted_ranking": (
                "kill_score descending; on ties, promising_score ascending"
            ),
            "true_ranking": (
                "power violation first; then larger excess above the "
                f"{power_degradation_limit:.2%} power limit; then larger "
                "TNS degradation; then larger power degradation ratio"
            ),
            "baseline_group_count": len(group_rows),
            "macro_precision_at_k": (
                float(np.mean(precision_values))
                if precision_values.size
                else float("nan")
            ),
            "macro_recall_at_k": (
                float(np.mean(precision_values))
                if precision_values.size
                else float("nan")
            ),
            "total_top_k_overlap": total_overlap,
            "rank_output": True,
        }

    kill_confusion = np.zeros((2, 2), dtype=np.int64)
    for index in range(len(prediction_rows)):
        if not bool(valid_decision[index]):
            continue
        kill_confusion[
            int(true_kill[index]),
            int(predicted_kill[index]),
        ] += 1

    per_metric: Dict[str, Any] = {}
    metric_accuracies: List[float] = []
    metric_macro_f1: List[float] = []

    for metric_index, metric_name in enumerate(metric_names):
        matrix = confusion[metric_index]
        count = int(matrix.sum())
        correct = int(np.trace(matrix))
        accuracy = safe_divide(correct, count)
        extra = multiclass_metrics(matrix)

        if math.isfinite(accuracy):
            metric_accuracies.append(accuracy)
        if math.isfinite(extra["macro_f1"]):
            metric_macro_f1.append(extra["macro_f1"])

        per_metric[metric_name] = {
            "count": count,
            "accuracy": accuracy,
            "confusion_matrix": matrix.tolist(),
            "class_order": list(CLASS_NAMES),
            **extra,
        }

    summary: Dict[str, Any] = {
        "split": split_name,
        "checkpoint": str(checkpoint_path),
        "checkpoint_epoch": checkpoint.get("epoch"),
        "device": str(device),
        "pair_count": len(dataset),
        "evaluated_samples": total_samples,
        "eval_prefix_ratio": config.data.eval_prefix_ratio,
        "average_cross_entropy": total_loss / max(total_samples, 1),
        "macro_accuracy_across_metrics": (
            float(np.mean(metric_accuracies))
            if metric_accuracies
            else float("nan")
        ),
        "macro_f1_across_metrics": (
            float(np.mean(metric_macro_f1))
            if metric_macro_f1
            else float("nan")
        ),
        "metrics": per_metric,
        "decision_scores": {
            "tns_metric": tns_metric_name,
            "power_metric": power_metric_name,
            "kill_score_source": "QoRComparator.compute_kill_score",
            "promising_score_source": "QoRComparator.compute_kill_score",
            "kill_score_statistics": score_statistics(predicted_kill_array),
            "promising_score_statistics": score_statistics(
                predicted_promising_array
            ),
            "promising_score_for_predicted_continue": score_statistics(
                predicted_promising_array[~predicted_kill]
            ),
            "promising_score_for_predicted_kill": score_statistics(
                predicted_promising_array[predicted_kill]
            ),
        },
        "killing": {
            **mode_details,
            **binary_metrics(kill_confusion),
        },
    }

    if args.kill_mode == "threshold":
        mode_suffix = (
            f"threshold_k{kill_threshold:g}_"
            f"tns{args.tns_significant_degradation:g}"
        )
    else:
        mode_suffix = f"ratio_{args.kill_ratio:g}_baseline"

    safe_mode_suffix = mode_suffix.replace(".", "p")
    summary_path = output_dir / f"{split_name}_{safe_mode_suffix}_summary.json"
    predictions_path = (
        output_dir / f"{split_name}_{safe_mode_suffix}_predictions.csv"
    )
    groups_path = output_dir / f"{split_name}_{safe_mode_suffix}_groups.csv"

    summary_path.write_text(
        json.dumps(json_ready(summary), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if prediction_rows:
        with predictions_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=list(prediction_rows[0].keys()),
            )
            writer.writeheader()
            writer.writerows(prediction_rows)

    if args.kill_mode == "ratio" and group_rows:
        with groups_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=list(group_rows[0].keys()),
            )
            writer.writeheader()
            writer.writerows(group_rows)

    print(f"device={device}")
    print(f"split={split_name}")
    print(f"pairs={len(dataset)}")
    print(f"eval_prefix_ratio={config.data.eval_prefix_ratio}")
    print(
        "average_cross_entropy="
        f"{summary['average_cross_entropy']:.6f}"
    )
    print(
        "macro_accuracy="
        f"{summary['macro_accuracy_across_metrics']:.4f}"
    )
    print(f"macro_f1={summary['macro_f1_across_metrics']:.4f}")

    killing = summary["killing"]
    print(
        "killing: "
        f"mode={killing['mode']}, "
        f"accuracy={killing['accuracy']}, "
        f"precision={killing['precision']}, "
        f"recall={killing['recall']}, "
        f"f1={killing['f1']}, "
        f"false_kill={killing['false_kill_count']}, "
        f"missed_kill={killing['missed_kill_count']}"
    )

    if args.kill_mode == "ratio":
        print(
            "ratio top-k: "
            f"groups={killing['baseline_group_count']}, "
            f"macro_precision@k={killing['macro_precision_at_k']}, "
            f"macro_recall@k={killing['macro_recall_at_k']}, "
            f"total_overlap={killing['total_top_k_overlap']}"
        )

    print(f"summary written to: {summary_path}")
    print(f"pair predictions written to: {predictions_path}")
    if args.kill_mode == "ratio":
        print(f"baseline group metrics written to: {groups_path}")


if __name__ == "__main__":
    main()

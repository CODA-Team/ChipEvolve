##相比v1，标签设定的依据更改为：在统一cp0下重新评估得到的QoR

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple
import math
import random

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from .config import DataConfig, TargetMetricSpec


# 三分类标签约定。后续加权 killing 使用 WORSE 类的概率。
BETTER = 0
SIMILAR = 1
WORSE = 2
IGNORE_LABEL = -100
CLASS_NAMES = ("better", "similar", "worse")

# final_eval 是统一 CP0 下重新评估得到的“标签行”，不能送入 Transformer。
FINAL_EVAL_CHECKPOINT = "final_eval"

# CP 通常以有限小数保存；用于防止 CSV 浮点解析带来的极小误差。
CP_MATCH_ABS_TOL = 1e-6


@dataclass(frozen=True)
class RunInfo:
    run_id: str
    trajectory_path: Path
    split: str
    design: str = ""
    platform: str = ""
    variant: str = ""
    original_cp: float = float("nan")
    eval_cp0: float = float("nan")


@dataclass(frozen=True)
class TrajectoryRecord:
    """
    一个完整历史 run 的两部分数据。

    trajectory:
        原始后端流程产生的检查点轨迹，用作模型输入。
    final_eval:
        在统一 eval_cp0 下重新评估得到的最终结果，只用来生成标签。
    """

    trajectory: pd.DataFrame
    final_eval: pd.Series


class TrajectoryStore:
    """按需读取并缓存每个 ORFS run 的 QoR 轨迹。"""

    def __init__(self, run_manifest: Path, config: DataConfig) -> None:
        self.config = config
        self.run_manifest_path = run_manifest
        self.base_dir = run_manifest.parent
        self.runs = self._read_run_manifest(run_manifest)
        self._cache: Dict[str, TrajectoryRecord] = {}

    @staticmethod
    def _positive_float(value: Any, field_name: str, run_id: str) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"run_id={run_id} 的 {field_name} 不是有效数字: {value!r}"
            ) from exc

        if not math.isfinite(result) or result <= 0:
            raise ValueError(
                f"run_id={run_id} 的 {field_name} 必须为有限正数，当前为 {result}"
            )
        return result

    def _read_run_manifest(self, path: Path) -> Dict[str, RunInfo]:
        frame = pd.read_csv(path)
        required = {
            "run_id",
            "trajectory_path",
            self.config.split_column,
            "original_cp",
            "eval_cp0",
        }
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"run manifest 缺少列: {sorted(missing)}")

        result: Dict[str, RunInfo] = {}
        for row in frame.to_dict(orient="records"):
            run_id = str(row["run_id"])
            raw_path = Path(str(row["trajectory_path"]))
            trajectory_path = (
                raw_path if raw_path.is_absolute() else self.base_dir / raw_path
            )
            if run_id in result:
                raise ValueError(f"run_id 重复: {run_id}")

            result[run_id] = RunInfo(
                run_id=run_id,
                trajectory_path=trajectory_path,
                split=str(row[self.config.split_column]),
                design=str(row.get("design", "")),
                platform=str(row.get("platform", "")),
                variant=str(row.get("variant", "")),
                original_cp=self._positive_float(
                    row["original_cp"], "original_cp", run_id
                ),
                eval_cp0=self._positive_float(
                    row["eval_cp0"], "eval_cp0", run_id
                ),
            )
        return result

    def get_info(self, run_id: str) -> RunInfo:
        try:
            return self.runs[run_id]
        except KeyError as exc:
            raise KeyError(f"run manifest 中不存在 run_id={run_id}") from exc

    def load(self, run_id: str) -> TrajectoryRecord:
        if run_id in self._cache:
            return self._cache[run_id]

        info = self.get_info(run_id)
        if not info.trajectory_path.exists():
            raise FileNotFoundError(f"轨迹文件不存在: {info.trajectory_path}")

        frame = pd.read_csv(info.trajectory_path)
        needed = {self.config.checkpoint_column, *self.config.input_metrics}
        # 目标指标可以与 input_metrics 同名，也可以是独立的 *_eval 列。
        needed.update(spec.name for spec in self.config.target_metrics)
        missing = needed - set(frame.columns)
        if missing:
            raise ValueError(
                f"{info.trajectory_path} 缺少 QoR/检查点列: {sorted(missing)}"
            )

        checkpoint_column = self.config.checkpoint_column
        checkpoint_names = frame[checkpoint_column].astype(str)

        # final_eval 必须恰好一行：它是统一 CP0 下的最终标签来源。
        final_eval_mask = checkpoint_names == FINAL_EVAL_CHECKPOINT
        final_eval_count = int(final_eval_mask.sum())
        if final_eval_count != 1:
            raise ValueError(
                f"{info.trajectory_path} 必须恰好包含一行 "
                f"{checkpoint_column}={FINAL_EVAL_CHECKPOINT!r},"
                f"当前找到 {final_eval_count} 行"
            )

        final_eval = frame.loc[final_eval_mask].iloc[0].copy()
        trajectory = frame.loc[~final_eval_mask].copy()

        if trajectory.empty:
            raise ValueError(f"{info.trajectory_path} 除 final_eval 外没有轨迹检查点")

        checkpoint_to_index = {
            name: index for index, name in enumerate(self.config.checkpoint_order)
        }
        trajectory_names = trajectory[checkpoint_column].astype(str)
        unknown = sorted(set(trajectory_names) - set(checkpoint_to_index))
        if unknown:
            raise ValueError(
                f"{info.trajectory_path} 出现未配置的轨迹检查点: {unknown}"
            )

        trajectory["__checkpoint_index"] = trajectory_names.map(checkpoint_to_index)
        trajectory = trajectory.sort_values(
            "__checkpoint_index", kind="stable"
        ).reset_index(drop=True)

        if trajectory[checkpoint_column].duplicated().any():
            duplicated = trajectory.loc[
                trajectory[checkpoint_column].duplicated(),
                checkpoint_column,
            ].tolist()
            raise ValueError(f"{info.trajectory_path} 检查点重复: {duplicated}")

        record = TrajectoryRecord(
            trajectory=trajectory,
            final_eval=final_eval,
        )
        self._cache[run_id] = record
        return record


class QoRPairDataset(Dataset[Dict[str, Any]]):
    """
    baseline 完整原生轨迹 + ongoing 部分原生轨迹的数据集。

    final_eval 行不进入模型，只用于在共同 eval_cp0 下生成最终标签。

    归一化沿用论文的配对方式：
    1. 对当前 baseline 的完整原生轨迹，逐 QoR 计算均值和标准差；
    2. baseline 与 ongoing 都使用这同一组 baseline 统计量标准化；
    3. 每个 baseline-ongoing pair 独立计算，不使用全数据集统计量。
    """

    def __init__(
        self,
        config: DataConfig,
        split: str,
        training: bool,
        seed: int = 42,
    ) -> None:
        self.config = config
        self.split = split
        self.training = training
        self.rng = random.Random(seed)
        self.store = TrajectoryStore(config.run_manifest, config)
        self.checkpoint_to_id = {
            name: index for index, name in enumerate(config.checkpoint_order)
        }
        self.pairs = self._read_pair_manifest(config.pair_manifest, split)

        # evaluate.py 需要连续的 final_eval 真值，独立构造业务决策标签和 ratio 模式下的真实排序。这里根据 target_metrics 自动定位
        # TNS 和 total power 对应列。
        self.final_tns_metric_name = self._resolve_final_metric_name("tns")
        self.final_power_metric_name = self._resolve_final_metric_name("power")

    def _resolve_final_metric_name(self, kind: str) -> str:
        """从 target_metrics 中自动定位 final TNS 或 final total power。"""
        scored: List[Tuple[int, str]] = []

        for spec in self.config.target_metrics:
            name = spec.name
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
                raise ValueError(f"未知 final metric 类型: {kind}")

            scored.append((score, name))

        if not scored:
            raise ValueError(
                f"无法从 target_metrics 中识别 final {kind} 指标。"
                f"当前目标为 {[spec.name for spec in self.config.target_metrics]}"
            )

        scored.sort(reverse=True)
        best_score = scored[0][0]
        best_names = [name for score, name in scored if score == best_score]
        if len(best_names) != 1:
            raise ValueError(f"final {kind} 指标识别存在歧义: {best_names}")

        return best_names[0]

    @property
    def raw_feature_dim(self) -> int:
        metric_dim = len(self.config.input_metrics)
        return metric_dim * 2 if self.config.append_missing_mask else metric_dim

    @property
    def num_targets(self) -> int:
        return len(self.config.target_metrics)

    def _validate_pair_metadata(
        self,
        baseline_run_id: str,
        ongoing_run_id: str,
        expected_split: str,
    ) -> None:
        if baseline_run_id == ongoing_run_id:
            raise ValueError("baseline_run_id 与 ongoing_run_id 不能相同")

        b_info = self.store.get_info(baseline_run_id)
        c_info = self.store.get_info(ongoing_run_id)

        if b_info.split != c_info.split:
            raise ValueError(
                f"pair 跨 split: {b_info.run_id}({b_info.split}) vs "
                f"{c_info.run_id}({c_info.split})"
            )
        if b_info.split != expected_split:
            raise ValueError(
                f"pair 的 run split={b_info.split!r},"
                f"但当前数据集 split={expected_split!r}"
            )

        if b_info.platform != c_info.platform:
            raise ValueError(
                f"pair 跨 platform: {b_info.platform!r} vs {c_info.platform!r}"
            )
        if b_info.design != c_info.design:
            raise ValueError(
                f"pair 跨 design: {b_info.design!r} vs {c_info.design!r}"
            )

        # original_cp 允许不同；统一评价用的 eval_cp0 必须相同。
        if not math.isclose(
            b_info.eval_cp0,
            c_info.eval_cp0,
            rel_tol=0.0,
            abs_tol=CP_MATCH_ABS_TOL,
        ):
            raise ValueError(
                "pair 的 eval_cp0 不一致，不能直接比较统一重测结果: "
                f"{b_info.run_id}={b_info.eval_cp0}, "
                f"{c_info.run_id}={c_info.eval_cp0}"
            )

    def _read_pair_manifest(self, path: Path, split: str) -> List[Dict[str, Any]]:
        frame = pd.read_csv(path)
        required = {"baseline_run_id", "ongoing_run_id"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"pair manifest 缺少列: {sorted(missing)}")

        if self.config.split_column in frame.columns:
            frame = frame[
                frame[self.config.split_column].astype(str) == split
            ].copy()
        else:
            keep_rows: List[bool] = []
            for row in frame.to_dict(orient="records"):
                c_info = self.store.get_info(str(row["ongoing_run_id"]))
                keep_rows.append(c_info.split == split)
            frame = frame.loc[keep_rows].copy()

        rows = frame.to_dict(orient="records")
        if not rows:
            raise ValueError(f"split={split!r} 没有可用的 baseline-ongoing pair")

        for row in rows:
            self._validate_pair_metadata(
                baseline_run_id=str(row["baseline_run_id"]),
                ongoing_run_id=str(row["ongoing_run_id"]),
                expected_split=split,
            )
        return rows

    def __len__(self) -> int:
        return len(self.pairs)

    def _choose_prefix_length(self, full_length: int, row: Mapping[str, Any]) -> int:
        if full_length <= 0:
            raise ValueError("ongoing 原生轨迹为空")

        explicit_ratio = row.get("prefix_ratio")
        if explicit_ratio is not None and not pd.isna(explicit_ratio):
            ratio = float(explicit_ratio)
        elif self.training:
            ratio = self.rng.choice(self.config.train_prefix_ratios)
        else:
            ratio = self.config.eval_prefix_ratio

        if not (0.0 < ratio <= 1.0):
            raise ValueError(f"prefix_ratio 必须位于 (0, 1]，当前为 {ratio}")

        prefix_length = int(math.ceil(full_length * ratio))
        prefix_length = max(self.config.min_prefix_checkpoints, prefix_length)
        return min(full_length, prefix_length)

    def _validate_alignment(
        self,
        baseline_frame: pd.DataFrame,
        ongoing_prefix: pd.DataFrame,
    ) -> None:
        if not self.config.strict_checkpoint_alignment:
            return

        count = len(ongoing_prefix)
        baseline_names = (
            baseline_frame[self.config.checkpoint_column]
            .astype(str)
            .tolist()[:count]
        )
        ongoing_names = (
            ongoing_prefix[self.config.checkpoint_column]
            .astype(str)
            .tolist()
        )
        if baseline_names != ongoing_names:
            raise ValueError(
                "baseline 与 ongoing 的原生前缀检查点不一致。"
                f"\nbaseline prefix={baseline_names}"
                f"\nongoing prefix={ongoing_names}"
            )

    def _paper_pair_normalize(
        self,
        baseline_values: np.ndarray,
        ongoing_values: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """以完整 baseline 原生轨迹的统计量同时标准化两条轨迹。"""
        baseline_mask = np.isfinite(baseline_values)
        ongoing_mask = np.isfinite(ongoing_values)

        with np.errstate(invalid="ignore"):
            mean = np.nanmean(baseline_values, axis=0)
            std = np.nanstd(baseline_values, axis=0)

        if np.isnan(mean).any():
            bad_metrics = [
                self.config.input_metrics[i]
                for i, value in enumerate(mean)
                if np.isnan(value)
            ]
            raise ValueError(
                f"baseline 原生轨迹的以下输入指标全为缺失值: {bad_metrics}"
            )

        scale = np.maximum(std, self.config.normalization_eps)
        baseline_norm = (baseline_values - mean) / scale
        ongoing_norm = (ongoing_values - mean) / scale

        baseline_norm = np.nan_to_num(
            baseline_norm,
            nan=self.config.missing_value_fill,
            posinf=self.config.missing_value_fill,
            neginf=self.config.missing_value_fill,
        ).astype(np.float32)
        ongoing_norm = np.nan_to_num(
            ongoing_norm,
            nan=self.config.missing_value_fill,
            posinf=self.config.missing_value_fill,
            neginf=self.config.missing_value_fill,
        ).astype(np.float32)

        return (
            baseline_norm,
            ongoing_norm,
            baseline_mask.astype(np.float32),
            ongoing_mask.astype(np.float32),
        )

    def _build_features(
        self,
        normalized: np.ndarray,
        observed_mask: np.ndarray,
    ) -> np.ndarray:
        if self.config.append_missing_mask:
            return np.concatenate(
                [normalized, observed_mask], axis=-1
            ).astype(np.float32)
        return normalized.astype(np.float32)

    @staticmethod
    def _final_metric_value(final_eval: pd.Series, metric_name: str) -> float:
        """目标值只从 final_eval 行读取。"""
        value = final_eval[metric_name]
        return float(value) if pd.notna(value) else float("nan")

    @staticmethod
    def _make_label(
        baseline_value: float,
        ongoing_value: float,
        spec: TargetMetricSpec,
    ) -> int:
        if not (math.isfinite(baseline_value) and math.isfinite(ongoing_value)):
            return IGNORE_LABEL

        # improvement > 0 统一表示 ongoing 更好。
        if spec.direction == "higher":
            improvement = ongoing_value - baseline_value
        else:
            improvement = baseline_value - ongoing_value

        tolerance = max(
            spec.absolute_tolerance,
            spec.relative_tolerance * max(abs(baseline_value), 1e-12),
        )
        if improvement > tolerance:
            return BETTER
        if improvement < -tolerance:
            return WORSE
        return SIMILAR

    def __getitem__(self, index: int) -> Dict[str, Any]:
        row = self.pairs[index]
        baseline_run_id = str(row["baseline_run_id"])
        ongoing_run_id = str(row["ongoing_run_id"])

        b_info = self.store.get_info(baseline_run_id)
        c_info = self.store.get_info(ongoing_run_id)
        self._validate_pair_metadata(
            baseline_run_id,
            ongoing_run_id,
            expected_split=self.split,
        )

        baseline_record = self.store.load(baseline_run_id)
        ongoing_record = self.store.load(ongoing_run_id)

        baseline_frame = baseline_record.trajectory
        ongoing_full_frame = ongoing_record.trajectory

        # final_eval 不参与长度、prefix 或 progress 计算。
        prefix_length = self._choose_prefix_length(
            len(ongoing_full_frame), row
        )
        ongoing_prefix = ongoing_full_frame.iloc[:prefix_length].copy()
        self._validate_alignment(baseline_frame, ongoing_prefix)

        baseline_values = baseline_frame[
            self.config.input_metrics
        ].to_numpy(dtype=np.float64)
        ongoing_values = ongoing_prefix[
            self.config.input_metrics
        ].to_numpy(dtype=np.float64)

        b_norm, c_norm, b_observed, c_observed = self._paper_pair_normalize(
            baseline_values, ongoing_values
        )

        baseline_features = self._build_features(b_norm, b_observed)
        ongoing_features = self._build_features(c_norm, c_observed)

        baseline_checkpoint_ids = np.asarray(
            [
                self.checkpoint_to_id[name]
                for name in baseline_frame[
                    self.config.checkpoint_column
                ].astype(str)
            ],
            dtype=np.int64,
        )
        ongoing_checkpoint_ids = np.asarray(
            [
                self.checkpoint_to_id[name]
                for name in ongoing_prefix[
                    self.config.checkpoint_column
                ].astype(str)
            ],
            dtype=np.int64,
        )

        labels = []
        for spec in self.config.target_metrics:
            baseline_final = self._final_metric_value(
                baseline_record.final_eval, spec.name
            )
            ongoing_final = self._final_metric_value(
                ongoing_record.final_eval, spec.name
            )
            labels.append(
                self._make_label(baseline_final, ongoing_final, spec)
            )

        # 连续 final_eval 真值只用于评估和审计，不进入 Transformer。
        baseline_final_tns = self._final_metric_value(
            baseline_record.final_eval, self.final_tns_metric_name
        )
        ongoing_final_tns = self._final_metric_value(
            ongoing_record.final_eval, self.final_tns_metric_name
        )
        baseline_final_power = self._final_metric_value(
            baseline_record.final_eval, self.final_power_metric_name
        )
        ongoing_final_power = self._final_metric_value(
            ongoing_record.final_eval, self.final_power_metric_name
        )

        progress = prefix_length / max(
            len(self.config.checkpoint_order), 1
        )
        progress = min(float(progress), 1.0)

        # pair 已验证两者 eval_cp0 相同，因此统一使用 baseline 的值。
        eval_cp0 = b_info.eval_cp0
        baseline_clock_ratio = b_info.original_cp / eval_cp0
        ongoing_clock_ratio = c_info.original_cp / eval_cp0

        return {
            "baseline_features": torch.from_numpy(baseline_features),
            "baseline_checkpoint_ids": torch.from_numpy(
                baseline_checkpoint_ids
            ),
            "ongoing_features": torch.from_numpy(ongoing_features),
            "ongoing_checkpoint_ids": torch.from_numpy(
                ongoing_checkpoint_ids
            ),
            "progress": torch.tensor(
                [progress], dtype=torch.float32
            ),
            "baseline_clock_ratio": torch.tensor(
                [baseline_clock_ratio], dtype=torch.float32
            ),
            "ongoing_clock_ratio": torch.tensor(
                [ongoing_clock_ratio], dtype=torch.float32
            ),
            "labels": torch.tensor(labels, dtype=torch.long),
            "baseline_run_id": baseline_run_id,
            "ongoing_run_id": ongoing_run_id,
            "prefix_length": prefix_length,
            # 以下仅用于日志、审计和调试，不直接送入模型。
            "baseline_original_cp": b_info.original_cp,
            "ongoing_original_cp": c_info.original_cp,
            "eval_cp0": eval_cp0,
            "baseline_final_tns": torch.tensor(
                baseline_final_tns, dtype=torch.float64
            ),
            "ongoing_final_tns": torch.tensor(
                ongoing_final_tns, dtype=torch.float64
            ),
            "baseline_final_power": torch.tensor(
                baseline_final_power, dtype=torch.float64
            ),
            "ongoing_final_power": torch.tensor(
                ongoing_final_power, dtype=torch.float64
            ),
        }


def _pad_2d(
    sequences: Sequence[torch.Tensor],
) -> Tuple[torch.Tensor, torch.Tensor]:
    """将 [T_i, D] 序列补齐为 [B, T_max, D]，并返回 valid mask。"""
    if not sequences:
        raise ValueError("empty batch")
    batch_size = len(sequences)
    max_length = max(tensor.shape[0] for tensor in sequences)
    feature_dim = sequences[0].shape[1]
    padded = torch.zeros(
        batch_size, max_length, feature_dim, dtype=torch.float32
    )
    valid_mask = torch.zeros(
        batch_size, max_length, dtype=torch.bool
    )
    for i, tensor in enumerate(sequences):
        length = tensor.shape[0]
        padded[i, :length] = tensor
        valid_mask[i, :length] = True
    return padded, valid_mask


def _pad_1d(sequences: Sequence[torch.Tensor]) -> torch.Tensor:
    if not sequences:
        raise ValueError("empty batch")
    batch_size = len(sequences)
    max_length = max(tensor.shape[0] for tensor in sequences)
    padded = torch.zeros(
        batch_size, max_length, dtype=torch.long
    )
    for i, tensor in enumerate(sequences):
        padded[i, : tensor.shape[0]] = tensor
    return padded


def collate_qor_pairs(
    batch: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """供 DataLoader 使用的变长序列 collate 函数。"""
    baseline_features, baseline_valid = _pad_2d(
        [item["baseline_features"] for item in batch]
    )
    ongoing_features, ongoing_valid = _pad_2d(
        [item["ongoing_features"] for item in batch]
    )

    return {
        "baseline_features": baseline_features,
        "baseline_checkpoint_ids": _pad_1d(
            [item["baseline_checkpoint_ids"] for item in batch]
        ),
        "baseline_valid_mask": baseline_valid,
        "ongoing_features": ongoing_features,
        "ongoing_checkpoint_ids": _pad_1d(
            [item["ongoing_checkpoint_ids"] for item in batch]
        ),
        "ongoing_valid_mask": ongoing_valid,
        "progress": torch.stack(
            [item["progress"] for item in batch], dim=0
        ),
        "baseline_clock_ratio": torch.stack(
            [item["baseline_clock_ratio"] for item in batch], dim=0
        ),
        "ongoing_clock_ratio": torch.stack(
            [item["ongoing_clock_ratio"] for item in batch], dim=0
        ),
        "labels": torch.stack(
            [item["labels"] for item in batch], dim=0
        ),
        "baseline_run_id": [
            item["baseline_run_id"] for item in batch
        ],
        "ongoing_run_id": [
            item["ongoing_run_id"] for item in batch
        ],
        "prefix_length": torch.tensor(
            [item["prefix_length"] for item in batch],
            dtype=torch.long,
        ),
        "baseline_original_cp": torch.tensor(
            [item["baseline_original_cp"] for item in batch],
            dtype=torch.float32,
        ),
        "ongoing_original_cp": torch.tensor(
            [item["ongoing_original_cp"] for item in batch],
            dtype=torch.float32,
        ),
        "eval_cp0": torch.tensor(
            [item["eval_cp0"] for item in batch],
            dtype=torch.float32,
        ),
        "baseline_final_tns": torch.stack(
            [item["baseline_final_tns"] for item in batch], dim=0
        ),
        "ongoing_final_tns": torch.stack(
            [item["ongoing_final_tns"] for item in batch], dim=0
        ),
        "baseline_final_power": torch.stack(
            [item["baseline_final_power"] for item in batch], dim=0
        ),
        "ongoing_final_power": torch.stack(
            [item["ongoing_final_power"] for item in batch], dim=0
        ),
    }

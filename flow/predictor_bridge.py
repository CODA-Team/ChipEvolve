"""Online adapter for the V2 Transformer QoR comparator.

The model consumes a complete native-clock baseline trajectory, a complete
prefix of an ongoing trajectory, and both runs' clock ratios to the campaign
CP0.  This module owns that contract and validates it before DRP uses a score.
"""
from __future__ import annotations

import csv
import hashlib
import inspect
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

_HERE = Path(__file__).resolve().parent
_PRED_DIR = _HERE / "predict_model"
_DEFAULT_CONFIG = _PRED_DIR / "example_config.json"
_DEFAULT_CHECKPOINT = _PRED_DIR / "best_model.pt"
_SIDECAR_VERSION = 2
_PS_TO_NS = 1.0e-3


class PredictorError(RuntimeError):
    """Base class for predictor integration failures."""


class PredictorConfigError(PredictorError):
    """The predictor configuration or runtime dependency is unavailable."""


class PredictorSchemaError(PredictorError):
    """The online data schema does not match the shipped V2 checkpoint."""


class PredictorDataError(PredictorError):
    """A trajectory or its clock metadata is malformed."""


class PredictorRuntimeError(PredictorError):
    """The loaded model does not satisfy the expected V2 inference API."""


# Model checkpoint name -> (flow substep JSON, metric-key prefix in that JSON).
_CKPT_JSON: Dict[str, Tuple[str, str]] = {
    "post_floorplan": ("2_1_floorplan.json", "floorplan"),
    "post_global_placement": ("3_3_place_gp.json", "globalplace"),
    "post_place_resize": ("3_4_place_resized.json", "placeopt"),
    "post_detailed_placement": ("3_5_place_dp.json", "detailedplace"),
    "post_cts": ("4_1_cts.json", "cts"),
    "post_global_route": ("5_1_grt.json", "globalroute"),
    "final_report": ("6_report.json", "finish"),
}

# QoR CSV metric -> (OpenROAD JSON suffix, scale into the model's unit).
_METRIC_FIELDS: Dict[str, Tuple[str, float]] = {
    "setup_tns_ns": ("timing__setup__tns", _PS_TO_NS),
    "setup_wns_ns": ("timing__setup__ws", _PS_TO_NS),
    "power_total_w": ("power__total", 1.0),
    "power_leakage_w": ("power__leakage__total", 1.0),
    "instance_area_um2": ("design__instance__area", 1.0),
    "instance_count": ("design__instance__count", 1.0),
    # Kept only for callers that explicitly request the old V1 schema.
    "hold_wns_ns": ("timing__hold__ws", _PS_TO_NS),
    "utilization": ("design__instance__utilization", 1.0),
}

_LEGACY_INPUT_METRICS = [
    "setup_tns_ns",
    "setup_wns_ns",
    "hold_wns_ns",
    "power_total_w",
    "instance_area_um2",
    "utilization",
]


def _load_raw_config(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PredictorConfigError(f"predictor config does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictorConfigError(f"cannot read predictor config {path}: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("data"), dict):
        raise PredictorConfigError(f"predictor config has no data object: {path}")
    return raw


def _schema_from_raw(raw: Mapping[str, Any]) -> Dict[str, Any]:
    data = raw.get("data")
    if not isinstance(data, Mapping):
        raise PredictorSchemaError("predictor config data section is not an object")

    input_metrics = [str(item) for item in data.get("input_metrics", [])]
    checkpoint_order = [str(item) for item in data.get("checkpoint_order", [])]
    target_specs = data.get("target_metrics", [])
    if not isinstance(target_specs, list):
        raise PredictorSchemaError("target_metrics must be a list")
    targets = [
        {
            "name": str(item.get("name")),
            "direction": str(item.get("direction")),
            "relative_tolerance": float(item.get("relative_tolerance", 0.01)),
            "absolute_tolerance": float(item.get("absolute_tolerance", 0.0)),
        }
        for item in target_specs
        if isinstance(item, Mapping)
    ]

    if not input_metrics or len(input_metrics) != len(set(input_metrics)):
        raise PredictorSchemaError("input_metrics must be non-empty and unique")
    unsupported_metrics = sorted(set(input_metrics) - set(_METRIC_FIELDS))
    if unsupported_metrics:
        raise PredictorSchemaError(
            f"no OpenROAD JSON mapping for input metrics: {unsupported_metrics}"
        )
    if not checkpoint_order or len(checkpoint_order) != len(set(checkpoint_order)):
        raise PredictorSchemaError("checkpoint_order must be non-empty and unique")
    unsupported_checkpoints = sorted(set(checkpoint_order) - set(_CKPT_JSON))
    if unsupported_checkpoints:
        raise PredictorSchemaError(
            f"no OpenROAD JSON mapping for checkpoints: {unsupported_checkpoints}"
        )
    if len(targets) != len(target_specs) or not targets:
        raise PredictorSchemaError("target_metrics contains an invalid entry")

    return {
        "input_metrics": input_metrics,
        "checkpoint_order": checkpoint_order,
        "append_missing_mask": bool(data.get("append_missing_mask", True)),
        "normalization_eps": float(data.get("normalization_eps", 1.0e-6)),
        "missing_value_fill": float(data.get("missing_value_fill", 0.0)),
        "target_metrics": targets,
    }


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _schema_sha256(schema: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(schema).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PredictorConfigError(f"cannot hash predictor checkpoint {path}: {exc}") from exc
    return digest.hexdigest()


def _resolve_config_path(config_path: Optional[Path]) -> Path:
    if config_path is None:
        return _DEFAULT_CONFIG
    requested = Path(config_path)
    if requested.exists():
        return requested
    # The pre-V2 driver used this filename. Treat it as an alias, not as a
    # generic fallback for arbitrary misspelled paths.
    if requested.name == "predictor_config.json" and _DEFAULT_CONFIG.exists():
        return _DEFAULT_CONFIG
    raise PredictorConfigError(f"predictor config does not exist: {requested}")


def _resolve_checkpoint_path(checkpoint_path: Optional[Path]) -> Path:
    resolved = Path(checkpoint_path) if checkpoint_path is not None else _DEFAULT_CHECKPOINT
    if not resolved.is_file():
        raise PredictorConfigError(f"predictor checkpoint does not exist: {resolved}")
    return resolved


_REFERENCE_SCHEMA = _schema_from_raw(_load_raw_config(_DEFAULT_CONFIG))
MODEL_INPUT_METRICS = list(_REFERENCE_SCHEMA["input_metrics"])
INPUT_METRICS = list(_LEGACY_INPUT_METRICS)  # V1 low-level helper compatibility.


def _prefix_through(order: Sequence[str], checkpoint: str) -> List[str]:
    try:
        end = list(order).index(checkpoint)
    except ValueError as exc:
        raise PredictorSchemaError(
            f"checkpoint_order does not contain required checkpoint {checkpoint!r}"
        ) from exc
    return list(order[: end + 1])


def _stage_prefix(order: Sequence[str], stage: str) -> List[str]:
    if stage == "place":
        return _prefix_through(order, "post_detailed_placement")
    if stage == "cts":
        return _prefix_through(order, "post_cts")
    if stage == "final":
        return list(order)
    raise PredictorDataError(f"unsupported predictor stage: {stage!r}")


_STAGE_PREFIX: Dict[str, List[str]] = {
    stage: _stage_prefix(_REFERENCE_SCHEMA["checkpoint_order"], stage)
    for stage in ("place", "cts", "final")
}


def load_predictor_schema(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Return the validated, dependency-light online schema."""
    schema = _schema_from_raw(_load_raw_config(_resolve_config_path(config_path)))
    _validate_schema_against_reference(schema)
    return schema


def stage_prefix(stage: str, config_path: Optional[Path] = None) -> List[str]:
    """Return the exact checkpoint prefix required at a DRP decision stage."""
    return _stage_prefix(load_predictor_schema(config_path)["checkpoint_order"], stage)


@dataclass(frozen=True)
class PredictorBundle:
    config: Any
    model: Any
    torch: Any
    config_path: Path
    checkpoint_path: Path
    checkpoint_sha256: str
    schema: Dict[str, Any]
    tns_metric_index: int
    power_metric_index: int


@dataclass(frozen=True)
class BaselineTrajectory:
    names: List[str]
    values: np.ndarray
    run_id: int
    original_cp: float
    eval_cp0: float


def _resolve_target_index(target_names: Sequence[str], kind: str) -> int:
    scored: List[Tuple[int, int]] = []
    for index, name in enumerate(target_names):
        lowered = name.lower()
        if kind == "tns" and "tns" in lowered:
            score = 10 + (3 if "setup" in lowered else 0)
            score += 2 if "eval" in lowered or "final" in lowered else 0
            scored.append((score, index))
        elif kind == "power" and "power" in lowered:
            score = 10 + (3 if "total" in lowered else 0)
            score += 2 if "eval" in lowered or "final" in lowered else 0
            scored.append((score, index))
    if not scored:
        raise PredictorSchemaError(
            f"cannot identify {kind} target in target_metrics={list(target_names)}"
        )
    best_score = max(score for score, _ in scored)
    best = [index for score, index in scored if score == best_score]
    if len(best) != 1:
        raise PredictorSchemaError(f"ambiguous {kind} target in {list(target_names)}")
    return best[0]


def _validate_schema_against_reference(schema: Mapping[str, Any]) -> None:
    if dict(schema) != _REFERENCE_SCHEMA:
        raise PredictorSchemaError(
            "online config schema differs from predict_model/example_config.json; "
            f"expected_sha256={_schema_sha256(_REFERENCE_SCHEMA)}, "
            f"actual_sha256={_schema_sha256(schema)}"
        )


def preflight_predictor(
    config_path: Optional[Path] = None,
    checkpoint_path: Optional[Path] = None,
) -> PredictorBundle:
    """Load and exercise the V2 model, raising on every schema/API mismatch."""
    resolved_config = _resolve_config_path(config_path)
    resolved_checkpoint = _resolve_checkpoint_path(checkpoint_path)
    raw = _load_raw_config(resolved_config)
    schema = _schema_from_raw(raw)
    _validate_schema_against_reference(schema)

    try:
        if str(_PRED_DIR) not in sys.path:
            sys.path.insert(0, str(_PRED_DIR))
        import torch  # noqa: WPS433
        from qor_comparator.config import ExperimentConfig
        from qor_comparator.model import QoRComparator
    except Exception as exc:
        raise PredictorConfigError(
            "cannot import the V2 predictor; install compatible torch and numpy "
            f"in the python3 environment used by maindriver.sh: {exc}"
        ) from exc

    try:
        config = ExperimentConfig.from_json(resolved_config)
    except Exception as exc:
        raise PredictorConfigError(
            f"cannot construct ExperimentConfig from {resolved_config}: {exc}"
        ) from exc

    target_names = [spec.name for spec in config.data.target_metrics]
    expected_targets = [item["name"] for item in schema["target_metrics"]]
    if target_names != expected_targets:
        raise PredictorSchemaError(
            f"resolved target names {target_names} != config schema {expected_targets}"
        )

    input_dim = len(schema["input_metrics"]) * (
        2 if schema["append_missing_mask"] else 1
    )
    try:
        model = QoRComparator(
            input_dim=input_dim,
            num_checkpoints=len(schema["checkpoint_order"]),
            target_metric_names=target_names,
            config=config.model,
        )
        try:
            checkpoint = torch.load(
                resolved_checkpoint, map_location="cpu", weights_only=True
            )
        except TypeError:
            checkpoint = torch.load(resolved_checkpoint, map_location="cpu")
    except Exception as exc:
        raise PredictorRuntimeError(
            f"cannot load predictor checkpoint {resolved_checkpoint}: {exc}"
        ) from exc

    if not isinstance(checkpoint, Mapping) or "model_state_dict" not in checkpoint:
        raise PredictorSchemaError("checkpoint has no model_state_dict")
    saved_targets = checkpoint.get("target_metric_names")
    if saved_targets is None or list(saved_targets) != target_names:
        raise PredictorSchemaError(
            f"checkpoint target names {saved_targets!r} != config {target_names!r}"
        )

    state = checkpoint["model_state_dict"]
    try:
        projection_shape = tuple(
            state["trajectory_encoder.input_projection.weight"].shape
        )
        embedding_shape = tuple(
            state["trajectory_encoder.checkpoint_embedding.weight"].shape
        )
    except (KeyError, AttributeError) as exc:
        raise PredictorSchemaError(
            "checkpoint lacks V2 input projection/checkpoint embedding weights"
        ) from exc
    if projection_shape[1] != input_dim:
        raise PredictorSchemaError(
            f"checkpoint input_dim={projection_shape[1]} != schema input_dim={input_dim}"
        )
    if embedding_shape[0] != len(schema["checkpoint_order"]):
        raise PredictorSchemaError(
            "checkpoint embedding count does not match checkpoint_order: "
            f"{embedding_shape[0]} != {len(schema['checkpoint_order'])}"
        )

    try:
        model.load_state_dict(state, strict=True)
        model.eval()
    except Exception as exc:
        raise PredictorSchemaError(f"checkpoint state_dict is incompatible: {exc}") from exc

    forward_params = inspect.signature(model.forward).parameters
    required_forward = {
        "baseline_features",
        "baseline_checkpoint_ids",
        "baseline_valid_mask",
        "ongoing_features",
        "ongoing_checkpoint_ids",
        "ongoing_valid_mask",
        "progress",
        "baseline_clock_ratio",
        "ongoing_clock_ratio",
    }
    missing_forward = sorted(required_forward - set(forward_params))
    if missing_forward:
        raise PredictorRuntimeError(
            f"QoRComparator.forward lacks V2 arguments: {missing_forward}"
        )

    score_params = inspect.signature(model.compute_kill_score).parameters
    required_score = {"probabilities", "tns_metric_index", "power_metric_index"}
    missing_score = sorted(required_score - set(score_params))
    if missing_score:
        raise PredictorRuntimeError(
            f"compute_kill_score lacks V2 arguments: {missing_score}"
        )

    tns_index = _resolve_target_index(target_names, "tns")
    power_index = _resolve_target_index(target_names, "power")
    targets = schema["target_metrics"]
    if targets[tns_index]["direction"] != "higher":
        raise PredictorSchemaError(
            "setup TNS target must use direction='higher' (less-negative TNS is better)"
        )
    if targets[power_index]["direction"] != "lower":
        raise PredictorSchemaError("total-power target must use direction='lower'")

    # A tiny forward pass catches return-contract drift before any run is killed.
    baseline_len = len(schema["checkpoint_order"])
    ongoing_len = len(_stage_prefix(schema["checkpoint_order"], "place"))
    with torch.no_grad():
        outputs = model(
            baseline_features=torch.zeros(1, baseline_len, input_dim),
            baseline_checkpoint_ids=torch.arange(baseline_len).unsqueeze(0),
            baseline_valid_mask=torch.ones(1, baseline_len, dtype=torch.bool),
            ongoing_features=torch.zeros(1, ongoing_len, input_dim),
            ongoing_checkpoint_ids=torch.arange(ongoing_len).unsqueeze(0),
            ongoing_valid_mask=torch.ones(1, ongoing_len, dtype=torch.bool),
            progress=torch.tensor([[ongoing_len / baseline_len]], dtype=torch.float32),
            baseline_clock_ratio=torch.ones(1, 1),
            ongoing_clock_ratio=torch.ones(1, 1),
        )
        if not isinstance(outputs, Mapping) or "probabilities" not in outputs:
            raise PredictorRuntimeError("V2 forward result has no probabilities tensor")
        score_outputs = model.compute_kill_score(
            outputs["probabilities"],
            tns_metric_index=tns_index,
            power_metric_index=power_index,
        )
    expected_score_keys = {
        "kill_score",
        "promising_score",
        "power_violation_probability",
        "power_feasible_probability",
        "tns_worse_probability",
        "tns_better_probability",
    }
    if not isinstance(score_outputs, Mapping):
        raise PredictorRuntimeError("compute_kill_score must return a mapping")
    missing_keys = sorted(expected_score_keys - set(score_outputs))
    if missing_keys:
        raise PredictorRuntimeError(
            f"compute_kill_score result lacks fields: {missing_keys}"
        )

    return PredictorBundle(
        config=config,
        model=model,
        torch=torch,
        config_path=resolved_config,
        checkpoint_path=resolved_checkpoint,
        checkpoint_sha256=_file_sha256(resolved_checkpoint),
        schema=schema,
        tns_metric_index=tns_index,
        power_metric_index=power_index,
    )


def _metric_row(
    json_dir: Path,
    checkpoint: str,
    input_metrics: Optional[Sequence[str]] = None,
) -> Optional[List[float]]:
    """Read one checkpoint row; a missing checkpoint means an incomplete prefix."""
    metrics = list(input_metrics or _LEGACY_INPUT_METRICS)
    if checkpoint not in _CKPT_JSON:
        raise PredictorSchemaError(f"unsupported checkpoint: {checkpoint!r}")
    filename, prefix = _CKPT_JSON[checkpoint]
    path = Path(json_dir) / filename
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictorDataError(f"cannot parse trajectory checkpoint {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise PredictorDataError(f"trajectory checkpoint is not a JSON object: {path}")

    row: List[float] = []
    for metric in metrics:
        try:
            suffix, scale = _METRIC_FIELDS[metric]
        except KeyError as exc:
            raise PredictorSchemaError(f"unsupported input metric: {metric!r}") from exc
        value = payload.get(f"{prefix}__{suffix}")
        try:
            numeric = float(value) * scale
        except (TypeError, ValueError):
            numeric = float("nan")
        row.append(numeric if math.isfinite(numeric) else float("nan"))
    return row


def build_trajectory(
    json_dir: Path,
    checkpoints: Sequence[str],
    input_metrics: Optional[Sequence[str]] = None,
) -> Optional[Tuple[List[str], np.ndarray]]:
    """Build the contiguous available prefix requested by ``checkpoints``."""
    names: List[str] = []
    rows: List[List[float]] = []
    for checkpoint in checkpoints:
        row = _metric_row(json_dir, checkpoint, input_metrics)
        if row is None:
            break
        names.append(checkpoint)
        rows.append(row)
    if not rows:
        return None
    return names, np.asarray(rows, dtype=np.float64)


def metric_row(
    json_dir: Path,
    checkpoint: str,
    config_path: Optional[Path] = None,
) -> Optional[List[float]]:
    """Read one checkpoint in the exact V2 config metric order."""
    schema = load_predictor_schema(config_path)
    return _metric_row(json_dir, checkpoint, schema["input_metrics"])


_MAKE_ASSIGNMENT = re.compile(
    r"^\s*(?:override\s+)?(?:export\s+)?SDC_FILE\s*(?::=|\?=|\+=|=)\s*(.*?)\s*$"
)
_MAKE_INCLUDE = re.compile(r"^\s*-?include\s+(.+?)\s*$")
_CLK_PERIOD = re.compile(
    r"^\s*set\s+clk_period\s+([0-9.eE+\-]+)(?:\s*(?:#.*)?)?$", re.MULTILINE
)


def _strip_make_comment(value: str) -> str:
    return value.split("#", 1)[0].strip().strip("'\"")


def _mirror_repo_path(path: Path) -> Optional[Path]:
    parts = path.parts
    for marker in ("designs", "predict_model"):
        if marker in parts:
            candidate = _HERE.joinpath(*parts[parts.index(marker):])
            if candidate.exists():
                return candidate
    return None


def _resolve_make_path(value: str, owner: Path, config_dir: Path) -> Path:
    expanded = os.path.expandvars(_strip_make_comment(value))
    # Generated configs occasionally retain a server-absolute repo prefix. Map
    # its designs/... suffix into the current checkout when needed.
    candidates: List[Path] = []
    raw = Path(expanded)
    if raw.is_absolute():
        candidates.append(raw)
        mirrored = _mirror_repo_path(raw)
        if mirrored is not None:
            candidates.append(mirrored)
    else:
        candidates.extend([owner.parent / raw, _HERE / raw, config_dir / raw])

    if "$" in expanded:
        suffix = re.sub(r"^.*?[})]/?", "", expanded)
        if suffix:
            candidates.append(config_dir / suffix)
    candidates.append(config_dir / raw.name)

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise PredictorDataError(
        f"SDC_FILE path {value!r} from {owner} cannot be resolved; "
        f"tried {[str(item) for item in candidates]}"
    )


def _find_sdc_file(
    config_path: Path,
    config_dir: Path,
    visited: Optional[set[Path]] = None,
) -> Optional[Path]:
    visited = visited or set()
    resolved_config = Path(config_path).resolve()
    if resolved_config in visited:
        raise PredictorDataError(f"recursive make include while reading {resolved_config}")
    visited.add(resolved_config)
    try:
        lines = resolved_config.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PredictorDataError(f"cannot read run config {resolved_config}: {exc}") from exc

    selected: Optional[Path] = None
    for line in lines:
        assignment = _MAKE_ASSIGNMENT.match(line)
        if assignment:
            selected = _resolve_make_path(assignment.group(1), resolved_config, config_dir)
            continue
        include = _MAKE_INCLUDE.match(line)
        if not include:
            continue
        include_value = _strip_make_comment(include.group(1))
        if not include_value or any(char in include_value for char in "*?"):
            continue
        try:
            include_path = _resolve_make_path(include_value, resolved_config, config_dir)
        except PredictorDataError:
            # A later explicit SDC_FILE assignment is sufficient; defer the
            # include error until we know no usable assignment exists.
            continue
        inherited = _find_sdc_file(include_path, config_dir, visited)
        if inherited is not None:
            selected = inherited
    return selected


def _positive_float(value: Any, context: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise PredictorDataError(f"{context} is not numeric: {value!r}") from exc
    if not math.isfinite(numeric) or numeric <= 0.0:
        raise PredictorDataError(f"{context} must be finite and positive: {numeric}")
    return numeric


def _positive_int(value: Any, context: str) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError) as exc:
        raise PredictorDataError(f"{context} is not an integer: {value!r}") from exc
    if numeric <= 0 or isinstance(value, float) and not value.is_integer():
        raise PredictorDataError(f"{context} must be a positive integer: {value!r}")
    return numeric


def _run_original_cp(config_dir: Path, run_id: int) -> float:
    sdc_path = resolve_run_sdc(config_dir, run_id)
    try:
        text = sdc_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PredictorDataError(f"cannot read SDC {sdc_path}: {exc}") from exc
    match = _CLK_PERIOD.search(text)
    if not match:
        raise PredictorDataError(f"no `set clk_period` found in {sdc_path}")
    return _positive_float(match.group(1), f"clk_period in {sdc_path}")


def resolve_run_sdc(config_dir: Path, run_id: int) -> Path:
    """Resolve the effective SDC_FILE selected by a generated run config."""
    run_config = Path(config_dir) / f"config_{int(run_id)}.mk"
    if not run_config.is_file():
        raise PredictorDataError(f"run config does not exist: {run_config}")
    sdc_path = _find_sdc_file(run_config, Path(config_dir))
    if sdc_path is None:
        raise PredictorDataError(f"no effective SDC_FILE found in {run_config}")
    return sdc_path


def read_run_original_cp(config_dir: Path, run_id: int) -> float:
    """Read a run's native clock period through its effective SDC_FILE."""
    return _run_original_cp(config_dir, run_id)


def compute_clock_ratios(
    baseline_original_cp: float,
    ongoing_original_cp: float,
    eval_cp0: float,
) -> Tuple[float, float]:
    """Validate clock metadata and return baseline/ongoing ratios to CP0."""
    baseline_cp = _positive_float(baseline_original_cp, "baseline original_cp")
    ongoing_cp = _positive_float(ongoing_original_cp, "ongoing original_cp")
    cp0 = _positive_float(eval_cp0, "eval_cp0")
    return baseline_cp / cp0, ongoing_cp / cp0


def _campaign_eval_cp0(config_dir: Path) -> float:
    path = Path(config_dir) / "cp0.txt"
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise PredictorDataError(f"cannot read campaign CP0 {path}: {exc}") from exc
    return _positive_float(value, f"eval_cp0 in {path}")


def _infer_run_id(json_dir: Path) -> int:
    match = re.fullmatch(r"run_(\d+)", Path(json_dir).name)
    if not match:
        raise PredictorDataError(
            f"cannot infer run_id from trajectory directory {json_dir}; pass run_id explicitly"
        )
    return int(match.group(1))


def _sidecar_path(csv_path: Path) -> Path:
    return Path(csv_path).with_suffix(".meta.json")


def write_trajectory_csv(
    json_dir: Path,
    checkpoints: Sequence[str],
    out_csv: Path,
    *,
    run_id: Optional[int] = None,
    config_dir: Optional[Path] = None,
    config_path: Optional[Path] = None,
    checkpoint_path: Optional[Path] = None,
    eval_cp0: Optional[float] = None,
) -> bool:
    """Write a complete baseline trajectory and its mandatory V2 sidecar."""
    resolved_config = _resolve_config_path(config_path)
    resolved_checkpoint = _resolve_checkpoint_path(checkpoint_path)
    schema = _schema_from_raw(_load_raw_config(resolved_config))
    _validate_schema_against_reference(schema)
    expected_order = schema["checkpoint_order"]
    if list(checkpoints) != expected_order:
        raise PredictorSchemaError(
            "baseline writer requires the complete configured checkpoint_order; "
            f"got {list(checkpoints)}, expected {expected_order}"
        )

    built = build_trajectory(json_dir, expected_order, schema["input_metrics"])
    if built is None or built[0] != expected_order:
        return False
    names, values = built

    baseline_run = int(run_id) if run_id is not None else _infer_run_id(json_dir)
    output = Path(out_csv)
    design_dir = Path(config_dir) if config_dir is not None else output.parent
    original_cp = _run_original_cp(design_dir, baseline_run)
    cp0 = (
        _positive_float(eval_cp0, "eval_cp0")
        if eval_cp0 is not None
        else _campaign_eval_cp0(design_dir)
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["checkpoint", *schema["input_metrics"]])
        for name, row in zip(names, values):
            writer.writerow(
                [name, *("" if np.isnan(value) else repr(float(value)) for value in row)]
            )

    sidecar = {
        "format_version": _SIDECAR_VERSION,
        "run_id": baseline_run,
        "original_cp": original_cp,
        "eval_cp0": cp0,
        "schema": schema,
        "schema_sha256": _schema_sha256(schema),
        "checkpoint_sha256": _file_sha256(resolved_checkpoint),
        "config_path": str(resolved_config),
        "checkpoint_path": str(resolved_checkpoint),
    }
    _sidecar_path(output).write_text(
        json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return True


def _read_baseline_csv(path: Path, bundle: PredictorBundle) -> Optional[BaselineTrajectory]:
    csv_path = Path(path)
    if not csv_path.exists():
        return None
    meta_path = _sidecar_path(csv_path)
    if not meta_path.is_file():
        raise PredictorDataError(
            f"baseline sidecar is missing: {meta_path}; regenerate the complete baseline"
        )
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictorDataError(f"cannot read baseline sidecar {meta_path}: {exc}") from exc
    if not isinstance(metadata, Mapping):
        raise PredictorDataError(f"baseline sidecar is not a JSON object: {meta_path}")
    if metadata.get("format_version") != _SIDECAR_VERSION:
        raise PredictorSchemaError(
            f"unsupported baseline sidecar version in {meta_path}: "
            f"{metadata.get('format_version')!r}"
        )
    if metadata.get("schema") != bundle.schema:
        raise PredictorSchemaError(
            f"baseline schema in {meta_path} does not match loaded predictor schema"
        )
    if metadata.get("schema_sha256") != _schema_sha256(bundle.schema):
        raise PredictorSchemaError(f"baseline schema hash is invalid in {meta_path}")
    if metadata.get("checkpoint_sha256") != bundle.checkpoint_sha256:
        raise PredictorSchemaError(
            "baseline was built for a different checkpoint; regenerate it: "
            f"sidecar={metadata.get('checkpoint_sha256')}, "
            f"loaded={bundle.checkpoint_sha256}"
        )

    expected_header = ["checkpoint", *bundle.schema["input_metrics"]]
    names: List[str] = []
    rows: List[List[float]] = []
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if header != expected_header:
                raise PredictorSchemaError(
                    f"baseline CSV header {header!r} != expected {expected_header!r}"
                )
            for line_number, fields in enumerate(reader, start=2):
                if len(fields) != len(expected_header):
                    raise PredictorDataError(
                        f"baseline CSV {csv_path}:{line_number} has {len(fields)} columns; "
                        f"expected {len(expected_header)}"
                    )
                names.append(fields[0])
                try:
                    rows.append(
                        [float(value) if value != "" else float("nan") for value in fields[1:]]
                    )
                except ValueError as exc:
                    raise PredictorDataError(
                        f"non-numeric baseline value at {csv_path}:{line_number}"
                    ) from exc
    except OSError as exc:
        raise PredictorDataError(f"cannot read baseline CSV {csv_path}: {exc}") from exc

    expected_order = bundle.schema["checkpoint_order"]
    if names != expected_order:
        raise PredictorSchemaError(
            f"baseline must contain all seven checkpoints in order; got {names}, "
            f"expected {expected_order}"
        )
    return BaselineTrajectory(
        names=names,
        values=np.asarray(rows, dtype=np.float64),
        run_id=_positive_int(metadata.get("run_id"), "baseline run_id"),
        original_cp=_positive_float(metadata.get("original_cp"), "baseline original_cp"),
        eval_cp0=_positive_float(metadata.get("eval_cp0"), "baseline eval_cp0"),
    )


def _normalize_pair(
    baseline: np.ndarray,
    ongoing: np.ndarray,
    eps: float,
    fill: float,
    append_mask: bool,
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply the same per-baseline normalization as the V2 training dataset."""
    baseline_mask = np.isfinite(baseline).astype(np.float32)
    ongoing_mask = np.isfinite(ongoing).astype(np.float32)
    with np.errstate(invalid="ignore"):
        mean = np.nanmean(baseline, axis=0)
        std = np.nanstd(baseline, axis=0)
    if np.isnan(mean).any():
        bad = np.flatnonzero(np.isnan(mean)).tolist()
        raise PredictorDataError(
            f"baseline has entirely missing model input column indexes: {bad}"
        )
    scale = np.maximum(std, eps)
    baseline_norm = np.nan_to_num(
        (baseline - mean) / scale, nan=fill, posinf=fill, neginf=fill
    )
    ongoing_norm = np.nan_to_num(
        (ongoing - mean) / scale, nan=fill, posinf=fill, neginf=fill
    )
    if append_mask:
        baseline_norm = np.concatenate([baseline_norm, baseline_mask], axis=-1)
        ongoing_norm = np.concatenate([ongoing_norm, ongoing_mask], axis=-1)
    return baseline_norm.astype(np.float32), ongoing_norm.astype(np.float32)


_SCORE_FIELDS = (
    "kill_score",
    "promising_score",
    "power_violation_probability",
    "power_feasible_probability",
    "tns_worse_probability",
    "tns_better_probability",
)


def _score_scalar(value: Any, field: str) -> float:
    try:
        numeric = float(value.detach().cpu().reshape(-1)[0].item())
    except Exception as exc:
        raise PredictorRuntimeError(f"score field {field!r} is not a scalar tensor") from exc
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise PredictorRuntimeError(f"score field {field!r} is outside [0,1]: {numeric}")
    return numeric


def predict_run_scores(
    run_ids: List[int],
    stage: str,
    logs_dir: Path,
    platform: str,
    design: str,
    baseline_csv: Path,
    config_path: Optional[Path] = None,
    checkpoint_path: Optional[Path] = None,
    config_dir: Optional[Path] = None,
) -> Optional[Dict[int, Optional[Dict[str, float]]]]:
    """Return V2 decision scores; incomplete run prefixes are left unscored."""
    bundle = preflight_predictor(config_path, checkpoint_path)
    baseline = _read_baseline_csv(Path(baseline_csv), bundle)
    if baseline is None:
        return None

    design_dir = (
        Path(config_dir)
        if config_dir is not None
        else Path(baseline_csv).parent
    )
    current_cp0 = _campaign_eval_cp0(design_dir)
    if not math.isclose(current_cp0, baseline.eval_cp0, rel_tol=0.0, abs_tol=1.0e-6):
        raise PredictorDataError(
            f"baseline eval_cp0={baseline.eval_cp0} != campaign cp0={current_cp0}"
        )

    checkpoint_order = bundle.schema["checkpoint_order"]
    prefix = _stage_prefix(checkpoint_order, stage)
    checkpoint_to_id = {name: index for index, name in enumerate(checkpoint_order)}
    baseline_ids = [checkpoint_to_id[name] for name in baseline.names]
    baseline_ratio, _ = compute_clock_ratios(
        baseline.original_cp, baseline.original_cp, current_cp0
    )
    progress = len(prefix) / len(checkpoint_order)
    torch = bundle.torch

    scores: Dict[int, Optional[Dict[str, float]]] = {}
    for run_id in run_ids:
        run_dir = Path(logs_dir) / platform / design / f"run_{int(run_id)}"
        built = build_trajectory(run_dir, prefix, bundle.schema["input_metrics"])
        if built is None or built[0] != prefix:
            scores[int(run_id)] = None
            continue
        ongoing_names, ongoing_values = built
        ongoing_cp = _run_original_cp(design_dir, int(run_id))
        _, ongoing_ratio = compute_clock_ratios(
            baseline.original_cp, ongoing_cp, current_cp0
        )
        baseline_features, ongoing_features = _normalize_pair(
            baseline.values,
            ongoing_values,
            float(bundle.schema["normalization_eps"]),
            float(bundle.schema["missing_value_fill"]),
            bool(bundle.schema["append_missing_mask"]),
        )
        ongoing_ids = [checkpoint_to_id[name] for name in ongoing_names]

        with torch.no_grad():
            outputs = bundle.model(
                baseline_features=torch.from_numpy(baseline_features).unsqueeze(0),
                baseline_checkpoint_ids=torch.tensor(baseline_ids).unsqueeze(0),
                baseline_valid_mask=torch.ones(1, len(baseline_ids), dtype=torch.bool),
                ongoing_features=torch.from_numpy(ongoing_features).unsqueeze(0),
                ongoing_checkpoint_ids=torch.tensor(ongoing_ids).unsqueeze(0),
                ongoing_valid_mask=torch.ones(1, len(ongoing_ids), dtype=torch.bool),
                progress=torch.tensor([[progress]], dtype=torch.float32),
                baseline_clock_ratio=torch.tensor([[baseline_ratio]], dtype=torch.float32),
                ongoing_clock_ratio=torch.tensor([[ongoing_ratio]], dtype=torch.float32),
            )
            if not isinstance(outputs, Mapping) or "probabilities" not in outputs:
                raise PredictorRuntimeError("V2 forward result has no probabilities tensor")
            score_outputs = bundle.model.compute_kill_score(
                outputs["probabilities"],
                tns_metric_index=bundle.tns_metric_index,
                power_metric_index=bundle.power_metric_index,
            )
        if not isinstance(score_outputs, Mapping):
            raise PredictorRuntimeError("compute_kill_score must return a mapping")
        missing = sorted(set(_SCORE_FIELDS) - set(score_outputs))
        if missing:
            raise PredictorRuntimeError(f"compute_kill_score lacks fields: {missing}")

        row = {field: _score_scalar(score_outputs[field], field) for field in _SCORE_FIELDS}
        row.update(
            {
                "progress": float(progress),
                "baseline_clock_ratio": float(baseline_ratio),
                "ongoing_clock_ratio": float(ongoing_ratio),
            }
        )
        scores[int(run_id)] = row
    return scores


def predict_kill_scores(
    run_ids: List[int],
    stage: str,
    logs_dir: Path,
    platform: str,
    design: str,
    baseline_csv: Path,
    config_path: Optional[Path] = None,
    checkpoint_path: Optional[Path] = None,
) -> Optional[Dict[int, Optional[float]]]:
    """Compatibility wrapper returning only each run's V2 kill score."""
    details = predict_run_scores(
        run_ids=run_ids,
        stage=stage,
        logs_dir=logs_dir,
        platform=platform,
        design=design,
        baseline_csv=baseline_csv,
        config_path=config_path,
        checkpoint_path=checkpoint_path,
        config_dir=Path(baseline_csv).parent,
    )
    if details is None:
        return None
    return {
        run_id: None if row is None else row["kill_score"]
        for run_id, row in details.items()
    }


def update_baseline_best(
    work_dir: Path,
    platform: str,
    design: str,
    iteration: int,
    objective: str,
    baseline_csv: Path,
    best_file: Path,
    config_path: Optional[Path] = None,
    checkpoint_path: Optional[Path] = None,
):
    """Persist the best clean full-survivor trajectory and its V2 metadata."""
    work_dir = Path(work_dir)
    metrics_path = work_dir / "tmp" / f"metrics_final_iter{iteration}.json"
    if not metrics_path.exists():
        return None
    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictorDataError(f"cannot read final metrics {metrics_path}: {exc}") from exc

    victims: set[int] = set()
    for stage in ("place", "cts"):
        path = work_dir / "tmp" / f"drp_{stage}_iter{iteration}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            victims.update(int(item) for item in payload.get("victim_ids", []))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise PredictorDataError(f"cannot read DRP victims {path}: {exc}") from exc

    if objective == "TNS_EVAL":
        from common import _power_base, tns_eval_obj

        try:
            power_budget = json.loads(
                (_HERE / "drp_config.json").read_text(encoding="utf-8")
            ).get("power_budget")
        except (OSError, json.JSONDecodeError) as exc:
            raise PredictorConfigError(f"cannot read drp_config.json: {exc}") from exc
        power_base = _power_base(platform, design)

        def objective_of(metric: Mapping[str, Any]) -> Optional[float]:
            return tns_eval_obj(metric, power_budget, power_base)

    else:

        def objective_of(metric: Mapping[str, Any]) -> Optional[float]:
            return metric.get(objective)

    candidates: List[Tuple[int, float]] = []
    for metric in metrics:
        run_id = int(metric["run_id"])
        value = objective_of(metric)
        if run_id not in victims and value is not None and math.isfinite(float(value)):
            candidates.append((run_id, float(value)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[1])

    best_path = Path(best_file)
    previous = float("inf")
    if best_path.exists():
        try:
            previous = float(best_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError) as exc:
            raise PredictorDataError(f"cannot read predictor best file {best_path}: {exc}") from exc

    design_dir = work_dir / "designs" / platform / design
    resolved_config = _resolve_config_path(config_path)
    resolved_checkpoint = _resolve_checkpoint_path(checkpoint_path)
    schema = load_predictor_schema(resolved_config)
    # Final metrics can be available from the combined log even when one native
    # checkpoint JSON is missing. Walk the objective-ordered candidates so such a
    # run cannot prevent a lower-ranked, genuinely complete survivor from becoming
    # the comparator baseline (especially during iteration-1 bootstrap).
    for best_run, best_objective in candidates:
        if best_objective >= previous:
            break
        run_dir = work_dir / "logs" / platform / design / f"run_{best_run}"
        saved = write_trajectory_csv(
            run_dir,
            schema["checkpoint_order"],
            Path(baseline_csv),
            run_id=best_run,
            config_dir=design_dir,
            config_path=resolved_config,
            checkpoint_path=resolved_checkpoint,
        )
        if saved:
            best_path.write_text(f"{best_objective}\n", encoding="utf-8")
            return best_run, best_objective
    return None

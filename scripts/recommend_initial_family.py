#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def load_json(path: Path):
    with path.open() as f:
        return json.load(f)


def size_class(instance_count: int) -> str:
    if instance_count >= 50000:
        return "very_large"
    if instance_count >= 20000:
        return "large"
    if instance_count >= 8000:
        return "medium"
    return "small"


def density_class(utilization: float) -> str:
    if utilization >= 0.65:
        return "dense"
    if utilization >= 0.45:
        return "moderate"
    return "relaxed"


def runtime_class(runtime_seconds: float) -> str:
    if runtime_seconds >= 30.0:
        return "heavy"
    if runtime_seconds >= 10.0:
        return "moderate"
    return "light"


def hpwl_class(delta_micron: float) -> str:
    if delta_micron >= 50000.0:
        return "extreme"
    if delta_micron >= 10000.0:
        return "high"
    if delta_micron >= 3000.0:
        return "elevated"
    return "manageable"


def timing_class(setup_ws: float, setup_tns: float) -> str:
    if setup_tns < 0.0 or setup_ws < 0.0:
        return "timing_stressed"
    return "timing_clean"


def recommend(metrics: dict):
    manifest = metrics.get("manifest", {})
    design_metrics = metrics.get("design_metrics", {})
    timing = metrics.get("timing_metrics", {})
    hpwl = metrics.get("hpwl_proxy", {})

    instance_count = int(design_metrics.get("instance_count", 0))
    utilization = float(design_metrics.get("utilization", 0.0))
    runtime_seconds = float(metrics.get("runtime_seconds", 0.0))
    hpwl_delta = float(hpwl.get("delta_micron", 0.0))
    setup_ws = float(timing.get("setup_ws", 0.0))
    setup_tns = float(timing.get("setup_tns", 0.0))

    features = {
        "design": manifest.get("design_config", "").split("/")[-2] if "/" in manifest.get("design_config", "") else None,
        "platform": manifest.get("design_config", "").split("/")[-3] if manifest.get("design_config", "").count("/") >= 2 else None,
        "instance_count": instance_count,
        "utilization": utilization,
        "runtime_seconds": runtime_seconds,
        "hpwl_delta_micron": hpwl_delta,
        "setup_ws": setup_ws,
        "setup_tns": setup_tns,
        "size_class": size_class(instance_count),
        "density_class": density_class(utilization),
        "runtime_class": runtime_class(runtime_seconds),
        "hpwl_class": hpwl_class(hpwl_delta),
        "timing_class": timing_class(setup_ws, setup_tns),
    }

    candidates = []

    def add(recipe, start_line, score, why, caution=None, variant_family=None):
        candidates.append(
            {
                "recipe": recipe,
                "start_line": start_line,
                "score": score,
                "why": why,
                "caution": caution or [],
                "variant_family": variant_family,
            }
        )

    if features["size_class"] in {"small", "medium"} and features["density_class"] != "dense":
        score = 2
        why = [
            "case is small/medium enough that a separate legalizer engine is practical",
            "LEGALM is now runtime-comparable on medium Nangate45 cases",
        ]
        if features["timing_class"] == "timing_stressed":
            score += 1
            why.append("timing is already stressed, so a different initializer is worth trying early")
        add(
            recipe="legalm_engine_initial",
            start_line="evolve_line",
            score=score,
            why=why,
            caution=[
                "materialize the legalm_engine family variant and build a dedicated OpenROAD binary first",
                "HPWL may still trail the current evolve-side negotiation family",
                "setup TNS is not yet consistently better than baseline",
            ],
            variant_family="legalm_engine",
        )

    base_score = 2
    why = [
        "runtime-aware negotiation family is the safest practical base",
        "it keeps evolve close to the current strong negotiation path",
    ]
    if features["size_class"] in {"large", "very_large"}:
        base_score += 2
        why.append("case is large, so bounded runtime matters immediately")
    if features["runtime_class"] == "heavy":
        base_score += 1
        why.append("baseline placement is already heavy, so avoid wide-postopt as the initial path")
    add(
        recipe="runtime_aware_net_family",
        start_line="evolve_line",
        score=base_score,
        why=why,
        caution=[
            "timing may still lag on large timing-stressed cases",
        ],
    )

    if features["size_class"] in {"large", "very_large"} and features["timing_class"] == "timing_stressed":
        add(
            recipe="runtime_aware_net_family_plus_priority_escape",
            start_line="evolve_line",
            score=5,
            why=[
                "large case is timing-stressed",
                "priority escape is the most relevant initial stack when main-pass escape quality matters",
            ],
            caution=[
                "runtime is usually above the plain runtime-aware base",
                "use this when timing matters more than minimal runtime",
            ],
        )

    if features["size_class"] == "small" and features["runtime_class"] == "light":
        add(
            recipe="hpwl_wide_postopt",
            start_line="evolve_line",
            score=1,
            why=[
                "small/light case can afford a quality-first exploratory donor run",
            ],
            caution=[
                "do not carry this forward as the default large-case base",
            ],
        )

    candidates.sort(key=lambda item: (-item["score"], item["recipe"]))
    return features, candidates


def main():
    parser = argparse.ArgumentParser(
        description="Recommend an initial evolve family from a baseline metrics.json."
    )
    parser.add_argument("--metrics", required=True, help="Path to baseline metrics.json")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args()

    metrics = load_json(Path(args.metrics))
    features, candidates = recommend(metrics)

    output = {"features": features, "recommendations": candidates}
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
        return

    print("Case features")
    for key in (
        "instance_count",
        "utilization",
        "runtime_seconds",
        "hpwl_delta_micron",
        "setup_ws",
        "setup_tns",
        "size_class",
        "density_class",
        "runtime_class",
        "hpwl_class",
        "timing_class",
    ):
        print(f"- {key}: {features[key]}")

    print("\nRecommended initial families")
    for idx, item in enumerate(candidates, start=1):
        print(f"{idx}. {item['recipe']}")
        print(f"   - start_line: {item['start_line']}")
        if item.get("variant_family"):
            print(f"   - variant_family: {item['variant_family']}")
        for reason in item["why"]:
            print(f"   - why: {reason}")
        for caution in item["caution"]:
            print(f"   - caution: {caution}")


if __name__ == "__main__":
    main()

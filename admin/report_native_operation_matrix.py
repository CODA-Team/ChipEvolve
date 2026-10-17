"""Freeze native operation pairs and report all attempts from independent oracles.

This is an offline experiment report, not an Agent loop or a business scorer.
Native Codex runs through the existing recorder; domain checks remain in the
separately pinned oracle program. Qualification runs never yield formal ratios.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from chip_evolve.config import read, write
from chip_evolve.jobs import digest

SCHEMA = "chip-evolve.native-operation-matrix.v1"
ARMS = ("direct", "platform")
TOKENS = ("input_tokens", "cached_input_tokens", "output_tokens")


def content_id(value: dict[str, Any]) -> str:
    body = {k: v for k, v in value.items() if k != "matrix_id"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def reference(path: str | Path) -> dict[str, str]:
    path = Path(path).resolve()
    return {"path": str(path), "sha256": digest(path)}


def freeze(request: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError("Keep the original frozen matrix")
    value = read(request)
    purpose = value["purpose"]
    if purpose not in {"qualification", "formal"}:
        raise ValueError("Declare qualification or formal purpose")
    rows, identities, pairs = [], set(), set()
    for pair in value["pairs"]:
        if pair["pair_id"] in pairs or set(pair["arms"]) != set(ARMS):
            raise ValueError("Distinct pair IDs and exactly two declared arms required")
        pairs.add(pair["pair_id"])
        arms, specifications = {}, []
        task = reference(pair["task"])
        for arm in ARMS:
            entry = pair["arms"][arm]
            episode = str(Path(entry["episode"]).resolve())
            if episode in identities:
                raise ValueError("An episode cannot count twice")
            identities.add(episode)
            spec = read(entry["specification"])
            if spec["schema"] != "chip-evolve.native-codex-episode.v1":
                raise ValueError("Use the existing native Codex recorder specification")
            specifications.append(spec)
            if purpose == "formal":
                if not spec.get("formal_episode") or Path(episode).exists():
                    raise ValueError("Formal attempts must be frozen before execution")
                if spec["input_hashes"].get(task["path"]) != task["sha256"]:
                    raise ValueError("Both formal arms must consume the same task")
                if any(
                    digest(Path(p)) != sha for p, sha in spec["input_hashes"].items()
                ):
                    raise ValueError("Formal episode inputs changed before freeze")
            arms[arm] = {
                "episode": episode,
                "specification": reference(entry["specification"]),
                "oracle": str(Path(entry["oracle"]).resolve()),
                "oracle_program": reference(entry["oracle_program"]),
            }
        a, b = specifications
        if a["native_command"] != b["native_command"]:
            raise ValueError("Paired attempts must use the same native Codex backend")
        for field in ("model", "reasoning_effort", "wall_seconds"):
            if a[field] != b[field]:
                raise ValueError("Paired model, effort and wall budgets must match")
        if purpose == "formal" and not pair["workload_equivalent"]:
            raise ValueError("Formal pairs require equivalent business workloads")
        rows.append(
            {
                "pair_id": pair["pair_id"],
                "design_id": pair["design_id"],
                "scenario": pair["scenario"],
                "task": task,
                "workload_equivalent": pair["workload_equivalent"],
                "model": a["model"],
                "reasoning_effort": a["reasoning_effort"],
                "wall_seconds": a["wall_seconds"],
                "arms": arms,
            }
        )
    if not rows:
        raise ValueError("A matrix must declare its denominator")
    result = {"schema": SCHEMA, "purpose": purpose, "pairs": rows}
    result["matrix_id"] = content_id(result)
    write(output, result)
    return result


def checked(path: Path) -> dict[str, Any]:
    value = read(path)
    if value["schema"] != SCHEMA or value["matrix_id"] != content_id(value):
        raise ValueError("Frozen matrix content changed")
    for pair in value["pairs"]:
        refs = [pair["task"]]
        for arm in pair["arms"].values():
            refs += [arm["specification"], arm["oracle_program"]]
        if any(digest(Path(r["path"])) != r["sha256"] for r in refs):
            raise ValueError("Frozen task, native specification or oracle changed")
    return value


def observe(entry: dict[str, Any]) -> dict[str, Any]:
    episode = Path(entry["episode"])
    path = episode / "receipt.json"
    result: dict[str, Any] = {
        "episode": str(episode),
        "execution_status": "not_started" if not episode.exists() else "unfinished",
        "correct": False,
        "correctness": "unverified",
        "usage_complete": False,
        "usage": None,
        "known_usage_lower_bound": None,
        "wall_seconds": None,
        "cost_pair_eligible": False,
    }
    if not path.exists():
        return result
    receipt = read(path)
    if receipt["specification_sha256"] != entry["specification"]["sha256"]:
        raise ValueError("Episode used another native specification")
    complete = receipt.get("usage_complete", False)
    usage = receipt["usage"] if complete else receipt.get("known_usage_lower_bound")
    if (complete or usage is not None) and (
        not isinstance(usage, dict)
        or any(type(usage.get(k)) is not int or usage[k] < 0 for k in TOKENS)
        or usage["cached_input_tokens"] > usage["input_tokens"]
    ):
        raise ValueError("Invalid native usage; unknown is not zero")
    result.update(
        receipt=reference(path),
        execution_status=receipt["status"],
        usage_complete=complete,
        usage=usage if complete else None,
        known_usage_lower_bound=usage,
        wall_seconds=receipt.get("wall_seconds"),
        cpu_usage=receipt.get("cpu_usage"),
        trace_problems=receipt.get("trace_problems", []),
    )
    oracle_path = Path(entry["oracle"])
    if oracle_path.exists():
        oracle = read(oracle_path)
        if (
            Path(oracle["episode"]).resolve() != episode
            or oracle["receipt_sha256"] != digest(path)
            or oracle["program_sha256"] != entry["oracle_program"]["sha256"]
        ):
            raise ValueError("Independent verdict is not bound to this attempt")
        evidence = oracle["evidence"]
        if digest(Path(evidence["path"])) != evidence["sha256"]:
            raise ValueError("Independent oracle evidence changed")
        if oracle["status"] not in {"passed", "failed"}:
            raise ValueError("An oracle must declare passed or failed")
        result.update(
            oracle=reference(oracle_path),
            correct=oracle["status"] == "passed",
            correctness=oracle["status"],
        )
    result["cost_pair_eligible"] = (
        result["correct"] and complete and receipt["status"] == "native_completed"
    )
    return result


def report(manifest: Path) -> dict[str, Any]:
    matrix = checked(manifest)
    pairs, all_attempts = [], []
    for pair in matrix["pairs"]:
        arms = {arm: observe(pair["arms"][arm]) for arm in ARMS}
        all_attempts += list(arms.values())
        eligible = (
            matrix["purpose"] == "formal"
            and pair["workload_equivalent"]
            and all(r["cost_pair_eligible"] for r in arms.values())
        )
        ratios = None
        if eligible:
            ratios = {}
            for key in ("input_plus_output_tokens", "wall_seconds"):
                values = {
                    arm: row["usage"]["input_tokens"] + row["usage"]["output_tokens"]
                    if key == "input_plus_output_tokens"
                    else row["wall_seconds"]
                    for arm, row in arms.items()
                }
                ratios[key] = {
                    **values,
                    "platform_over_direct": values["platform"] / values["direct"]
                    if values["direct"] > 0
                    else None,
                }
        pairs.append(
            {**pair, "outcomes": arms, "cost_comparable": eligible, "costs": ratios}
        )
    observed = [a for a in all_attempts if "receipt" in a]
    measured = [a for a in observed if a["known_usage_lower_bound"] is not None]
    known = {
        key: sum(a["known_usage_lower_bound"][key] for a in measured) for key in TOKENS
    }
    return {
        "matrix_id": matrix["matrix_id"],
        "purpose": matrix["purpose"],
        "planned_attempts": len(all_attempts),
        "observed_attempts": len(observed),
        "correct_attempts": sum(a["correct"] for a in all_attempts),
        "correct_rate_all_planned": sum(a["correct"] for a in all_attempts)
        / len(all_attempts),
        "unknown_usage_attempts": [
            a["episode"] for a in all_attempts if not a["usage_complete"]
        ],
        "known_usage_lower_bound": known,
        "known_input_plus_output_tokens": known["input_tokens"]
        + known["output_tokens"],
        "cost_comparable_pairs": sum(p["cost_comparable"] for p in pairs),
        "pairs": pairs,
        "limits": [
            "Independent oracle decides correctness; native exit alone is insufficient.",
            "All declared failures, missing and incomplete attempts remain in the denominator and known costs.",
            "Cached input is an input subset, never added to input plus output.",
            "Paired costs require formal equivalent workloads, both correct and both usage-complete.",
            "Native recorder CPU excludes independent EF/DF services and detached descendants; no full hostCPU ratio.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "report"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = (
        freeze(args.input, args.output)
        if args.action == "freeze"
        else report(args.input)
    )
    if args.action == "report":
        write(args.output, value)
    print(json.dumps({"output": str(args.output), "purpose": value["purpose"]}))


if __name__ == "__main__":
    main()

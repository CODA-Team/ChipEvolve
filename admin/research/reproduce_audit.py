"""Read-only source inventory and historical-paper aggregate verification.

Run from any directory with the standard-library Python interpreter. This does
not start services, open design databases, grade answers again, or run models.
Runtime output belongs under the workspace var directory.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def source_comparison(current: Path, historical: Path) -> dict:
    def inventory(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): digest(path)
            for path in root.rglob("*.py")
            if "__pycache__" not in path.parts
        }

    newer, older = inventory(current), inventory(historical)
    shared = newer.keys() & older.keys()
    return {
        "historical_source": str(historical),
        "current_source": str(current),
        "historical_module_count": len(older),
        "current_module_count": len(newer),
        "unchanged": sorted(key for key in shared if newer[key] == older[key]),
        "changed": sorted(key for key in shared if newer[key] != older[key]),
        "historical_only": sorted(older.keys() - newer.keys()),
        "current_only": sorted(newer.keys() - older.keys()),
        "limitation": "File retention and hash agreement do not prove behavior equivalence.",
    }


def paper_round(path: Path) -> dict:
    data = json.loads(path.read_text())
    rows = data["rows"]
    pairs: dict[tuple[str, str], dict] = defaultdict(dict)
    for row in rows:
        key = (row["design"], row["question_id"])
        arm = row["arm"]
        if arm in pairs[key]:
            raise ValueError(f"duplicate pair arm at {path}: {key}, {arm}")
        pairs[key][arm] = row
    if len(rows) != 144 or len(pairs) != 72:
        raise ValueError(f"expected the paper's 72-task paired round: {path}")
    complete = [
        pair for pair in pairs.values()
        if {"raw", "interface"} <= pair.keys()
        and all(
            pair[arm].get("usage_known")
            and isinstance(pair[arm].get("total_tokens"), (int, float))
            for arm in ("raw", "interface")
        )
    ]

    def total(arm: str, field: str) -> float:
        return sum(pair[arm][field] for pair in complete)

    return {
        "source_path": str(path),
        "source_sha256": digest(path),
        "model": data["model"],
        "episodes": len(rows),
        "tasks": len(pairs),
        "correct": {
            arm: sum(bool(row.get("passed")) for row in rows if row["arm"] == arm)
            for arm in ("raw", "interface")
        },
        "complete_usage_pairs": len(complete),
        "token_reduction_pct": 100 * (
            1 - total("interface", "total_tokens") / total("raw", "total_tokens")
        ),
        "online_time_reduction_pct": 100 * (
            1 - total("interface", "seconds") / total("raw", "seconds")
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--historical-code", type=Path, required=True)
    parser.add_argument("--historical-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repos = ("execution-foundation", "data-foundation", "data-interface", "query-agent")
    rounds = [
        paper_round(path)
        for path in sorted((args.historical_results / "next_models").glob(
            "*netgeometry-formal01/summary.json"
        ))
    ]
    if len(rounds) != 7:
        raise ValueError("expected seven independently identified historical paper rounds")
    ablations = []
    for path in sorted((args.historical_results / "final_ariane_ablations04").glob(
        "*/summary.json"
    )):
        data = json.loads(path.read_text())
        rows = data["rows"]
        ablations.append({
            "source_path": str(path), "source_sha256": digest(path),
            "model": data["model"], "episodes": len(rows),
            "correct": sum(bool(row.get("passed")) for row in rows),
            "total_tokens": sum(row.get("total_tokens", 0) or 0 for row in rows),
            "online_seconds": sum(row.get("seconds", 0) or 0 for row in rows),
            "tool_calls": sum(row.get("tool_calls", 0) or 0 for row in rows),
        })
    result = {
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "read-only hash inventory and re-aggregation of saved scored rows",
        "limitations": [
            "No new EDA or model benchmark was run.",
            "Saved passed fields were counted; gold and answer traces were not regraded.",
            "Historical results do not qualify the split projects as the same deployment.",
            "Costs omit preparation, cold startup, and a persistent-native-session raw baseline.",
        ],
        "repositories": {
            name: {"head": git(args.workspace / name, "rev-parse", "HEAD"),
                   "status": git(args.workspace / name, "status", "--short")}
            for name in repos
        },
        "data_source_comparison": source_comparison(
            args.workspace / "data-foundation/src/openroad_app_data_foundation",
            args.historical_code / "apps/data_foundation/src/openroad_app_data_foundation",
        ),
        "historical_paper_rounds": rounds,
        "historical_paper_totals": {
            "models": len(rounds), "episodes": sum(row["episodes"] for row in rounds),
            "complete_usage_pairs": sum(row["complete_usage_pairs"] for row in rounds),
        },
        "historical_paper_ablations": ablations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "sha256": digest(args.output),
                      "totals": result["historical_paper_totals"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

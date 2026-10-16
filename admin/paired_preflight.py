"""Paired native Codex candidate-fact pilot; no custom model/tool loop."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from admin.freeze_formal_campaign import checked
from chip_evolve.config import Deployment, read, write
from chip_evolve.environment import reference
from chip_evolve.validation import query_facts


def token_usage(events: list[dict[str, Any]]) -> dict[str, Any]:
    turns = [
        e["usage"] for e in events if e.get("type") == "turn.completed" and "usage" in e
    ]
    complete = (
        bool(turns)
        and not any(e.get("type") in {"error", "turn.failed"} for e in events)
        and all(
            type(t.get(k)) is int and t[k] >= 0
            for t in turns
            for k in ("input_tokens", "output_tokens")
        )
    )
    result: dict[str, Any] = {
        "complete": complete,
        "turns": turns,
        "total_tokens": None,
    }
    if complete:
        result.update(
            input_tokens=sum(t["input_tokens"] for t in turns),
            output_tokens=sum(t["output_tokens"] for t in turns),
        )
        result["total_tokens"] = result["input_tokens"] + result["output_tokens"]
    return result


def expected_facts(frame: dict[str, Any]) -> list[str]:
    """Independent benchmark oracle, using frozen native values and original bounds."""
    bounds = read(frame["objective"])["constraints"]
    mapping = {
        "setup_tns_ns_min": "finish__timing__setup__tns",
        "hold_tns_ns_min": "finish__timing__hold__tns",
        "max_slew_violations": "finish__timing__drv__max_slew",
        "max_cap_violations": "finish__timing__drv__max_cap",
        "placement_violations": "design__violations",
        "power_total_w_max": "finish__power__total",
        "cell_area_um2_max": "finish__design__instance__area",
        "core_area_um2_max": "finish__design__core__area",
        "die_area_um2_max": "finish__design__die__area",
    }
    failed = [
        name
        for name, key in mapping.items()
        if (
            frame["metrics"][key] < bounds[name]
            if name.endswith("_min")
            else frame["metrics"][key] > bounds[name]
        )
    ]
    if frame["route_drc"] > bounds["route_drc"]:
        failed.append("route_drc")
    return sorted(failed)


def correct(
    answer: dict[str, Any],
    design: str,
    expected: dict[str, list[str]],
    allowed: dict[str, set[str]],
) -> bool:
    feasible = [run for run, failed in expected.items() if not failed]
    rejected = {
        r["run_id"]: sorted(r["violations"]) for r in answer.get("rejected", [])
    }
    evidence = answer.get("evidence", [])
    return (
        answer.get("design_id") == design
        and sorted(answer.get("feasible_run_ids", [])) == sorted(feasible)
        and rejected == {run: v for run, v in expected.items() if v}
        and len(answer.get("rejected", [])) == len(rejected)
        and {r["run_id"] for r in evidence} == set(expected)
        and all(r["path"] in allowed[r["run_id"]] for r in evidence)
    )


def paired_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        groups.setdefault((row["design_id"], row["repeat"]), {})[row["arm"]] = row
    paired = []
    for (design, repeat), arms in groups.items():
        if set(arms) != {"direct", "platform"}:
            continue
        if all(
            r["correct"] and r["usage"]["complete"] and r["status"] == "succeeded"
            for r in arms.values()
        ):
            paired.append(
                {
                    "design_id": design,
                    "repeat": repeat,
                    "direct_tokens": arms["direct"]["usage"]["total_tokens"],
                    "platform_tokens": arms["platform"]["usage"]["total_tokens"],
                    "direct_seconds": arms["direct"]["wall_seconds"],
                    "platform_seconds": arms["platform"]["wall_seconds"],
                }
            )
    return {
        "attempts": len(rows),
        "correct_attempts": sum(bool(r["correct"]) for r in rows),
        "correct_pairs_with_complete_usage": len(paired),
        "paired_costs": paired,
        "unknown_usage_attempts": sum(not r["usage"]["complete"] for r in rows),
    }


def task_prompt(
    design: str, candidates: list[str], catalog: list[str], client_python: str
) -> str:
    return (
        "You are checking measured ASIC candidates under their ORIGINAL frozen constraints. "
        "List every feasible run; for every rejected run list ALL violated constraint keys. "
        "Cite an input path for every candidate. Do not choose a winner or infer causes. "
        "Both arms may use the same native Codex tools and write helper scripts in their workspace. "
        "Keep input designs/results read-only. Use only the supplied input catalog; do not inspect other episodes/answers. "
        "No new EDA or child model calls are needed for this read-only task. "
        f"Design: {design}. Target candidate run IDs (the complete answer scope): {json.dumps(candidates)}. "
        "Return facts and evidence for EXACTLY these runs. Any reference or baseline present in the inputs "
        "is context only and MUST NOT appear in the answer unless it is in that target list. "
        f"Input catalog: {json.dumps(catalog)}. "
        "Raw results point to original objective files. The compact view contains the same constraints and facts. "
        f"Python with installed public clients: {client_python}. Return the requested JSON."
    )


def run(
    manifest: Path,
    preparation: Path,
    output: Path,
    *,
    model: str,
    repeats: int,
    seconds: int,
) -> dict[str, Any]:
    campaign = checked(manifest)
    deployment = Deployment(Path(campaign["config"]["path"]))
    output.mkdir(parents=True, exist_ok=False)
    preparation_rows = json.loads(preparation.read_text())
    briefs = {
        r["design_id"]: r["brief"] for r in preparation_rows if r["returncode"] == 0
    }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "design_id": {"type": "string"},
            "feasible_run_ids": {"type": "array", "items": {"type": "string"}},
            "rejected": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "run_id": {"type": "string"},
                        "violations": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["run_id", "violations"],
                },
            },
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "run_id": {"type": "string"},
                        "path": {"type": "string"},
                    },
                    "required": ["run_id", "path"],
                },
            },
        },
        "required": ["design_id", "feasible_run_ids", "rejected", "evidence"],
    }
    schema_path = output / "answer-schema.json"
    write(schema_path, schema)
    write(
        output / "protocol.json",
        {
            "protocol_version": "candidate-fact-pilot-r2-explicit-targets",
            "campaign_id": campaign["campaign_id"],
            "model": model,
            "reasoning_effort": "medium",
            "repeats": repeats,
            "seconds_per_attempt": seconds,
            "order": "alternating within each pair",
            "scope": "Candidate fact checking only; direct arm also gets normalized result JSONs. No end-to-end efficiency or Query reasoning claim.",
            "preparation": reference(preparation),
            "manifest": reference(manifest),
            "briefs": {key: reference(Path(path)) for key, path in briefs.items()},
        },
    )
    rows, expectations = [], {}
    for repeat in range(repeats):
        for design in campaign["designs"]:
            name = design["design_id"]
            raw = [r["path"] for r in design["flow_candidates"]]
            expected = {}
            raw_evidence = {}
            for p in raw:
                frame = read(p)
                query_facts(deployment, frame)
                expected[frame["run_id"]] = expected_facts(frame)
                raw_evidence[frame["run_id"]] = {p}
            expectations[name] = expected
            brief = briefs[name]
            for arm in (
                ["direct", "platform"] if repeat % 2 == 0 else ["platform", "direct"]
            ):
                folder = output / f"{name}-{repeat}-{arm}"
                folder.mkdir()
                workspace = folder / "workspace"
                workspace.mkdir()
                catalog = raw if arm == "direct" else [brief]
                prompt = task_prompt(
                    name, list(expected), catalog, deployment.value["client_python"]
                )
                (folder / "prompt.txt").write_text(prompt)
                command = [
                    shutil.which("codex") or "codex",
                    "exec",
                    "--ignore-user-config",
                    "--ephemeral",
                    "--skip-git-repo-check",
                    "-C",
                    str(workspace),
                    "-s",
                    "danger-full-access",
                    "-m",
                    model,
                    "-c",
                    'model_reasoning_effort="medium"',
                    "-c",
                    'approval_policy="never"',
                    "--json",
                    "--output-schema",
                    str(schema_path),
                    "--output-last-message",
                    str(folder / "answer.json"),
                    "-",
                ]
                started = time.monotonic()
                code = None
                with (
                    (folder / "events.jsonl").open("w") as stdout,
                    (folder / "stderr.log").open("w") as stderr,
                ):
                    try:
                        code = subprocess.run(
                            command,
                            input=prompt,
                            text=True,
                            stdout=stdout,
                            stderr=stderr,
                            timeout=seconds,
                            check=False,
                            env={**os.environ, "PYTHONNOUSERSITE": "1"},
                        ).returncode
                    except subprocess.TimeoutExpired:
                        pass
                events, malformed = [], []
                for number, line in enumerate(
                    (folder / "events.jsonl").read_text().splitlines()
                ):
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        malformed.append(number)
                try:
                    answer = (
                        read(folder / "answer.json")
                        if (folder / "answer.json").exists()
                        else {}
                    )
                except json.JSONDecodeError:
                    answer = {}
                    malformed.append("answer")
                usage = token_usage(events)
                if code != 0 or malformed:
                    usage.update(complete=False, total_tokens=None)
                allowed = (
                    raw_evidence
                    if arm == "direct"
                    else {run: {brief} for run in expected}
                )
                row = {
                    "design_id": name,
                    "repeat": repeat,
                    "arm": arm,
                    "status": "succeeded"
                    if code == 0
                    else "timed_out"
                    if code is None
                    else "failed",
                    "returncode": code,
                    "wall_seconds": time.monotonic() - started,
                    "usage": usage,
                    "correct": code == 0
                    and not malformed
                    and correct(answer, name, expected, allowed),
                    "episode": str(folder),
                    "malformed_event_lines": malformed,
                    "tool_calls": sum(
                        e.get("type") == "item.completed"
                        and e.get("item", {}).get("type") == "command_execution"
                        for e in events
                    ),
                }
                rows.append(row)
                write(folder / "receipt.json", row)
                write(
                    output / "progress.json",
                    {"rows": rows, "summary": paired_summary(rows)},
                )
    value = {
        "rows": rows,
        "summary": paired_summary(rows),
        "interpretation": "Small paired candidate-fact pilot only. Preparation is separate; no general efficiency claim.",
    }
    write(output / "expected-after-run.json", expectations)
    write(output / "result.json", value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seconds", type=int, default=240)
    args = parser.parse_args()
    value = run(
        args.manifest.resolve(),
        args.preparation.resolve(),
        args.output.resolve(),
        model=args.model,
        repeats=args.repeats,
        seconds=args.seconds,
    )
    print(json.dumps(value["summary"]))


if __name__ == "__main__":
    main()

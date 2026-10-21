"""Export measured relay branches without inventing parents, metrics or adoption."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FIELDS = {
    "power_mw": ("finish__power__total", 1000),
    "instance_area_um2": ("finish__design__instance__area", 1),
    "core_area_um2": ("finish__design__core__area", 1),
    "die_area_um2": ("finish__design__die__area", 1),
    "setup_ws_ps": ("finish__timing__setup__ws", 1000),
    "setup_tns_ns": ("finish__timing__setup__tns", 1),
    "hold_ws_ps": ("finish__timing__hold__ws", 1000),
    "hold_tns_ns": ("finish__timing__hold__tns", 1),
    "slew_violations": ("finish__timing__drv__max_slew", 1),
    "cap_violations": ("finish__timing__drv__max_cap", 1),
    "fanout_violations": ("finish__timing__drv__max_fanout", 1),
    "placement_violations": ("design__violations", 1),
}


def ibex_validation_state(old: Path, result_sha256: str) -> str | None:
    """Distinguish the original proof's terminal outcome from physical QoR."""
    case = old / "runtime/experiments/ibex"
    proof = (
        case / "a29-ibex-ip3-final-cell-variant-proof-r1/final-functional-proof.json"
    )
    if proof.exists():
        record = json.loads(proof.read_text())
        evidence = record.get("proof", {})
        complete = (
            record.get("passed") is True
            and record.get("candidate_sha256") == result_sha256
            and evidence.get("proven_points") == 106
            and evidence.get("proven_partitions") == 2046
            and evidence.get("unproven_points") == 0
        )
        if not complete:
            return "physically measured; matching complete 106-output proof not established; not adopted"
        validation = case / "a29-ibex-ip3-final-delivery-replay-r3/validation.json"
        pointer = old / "runtime/designs/ibex/incumbent.json"
        if validation.exists() and pointer.exists():
            checked, selected = (
                json.loads(validation.read_text()),
                json.loads(pointer.read_text()),
            )
            if (
                checked.get("result_sha256") == result_sha256
                and all(
                    checked.get(key) is True
                    for key in ("passed", "replay_exact", "sdk_identity_passed")
                )
                and selected.get("result_sha256") == result_sha256
            ):
                return "validated and adopted: exact 106-output/2046-partition proof and independent replay"
        return "complete 106-output proof passed; independent replay/adoption not yet established"
    error = old / "ibex-native-continuation-terminal-error.json"
    if error.exists():
        record = json.loads(error.read_text())
        return (
            "physically measured; complete proof did not pass/finish; not adopted: "
            + record["type"]
        )
    return None


def measured_node(
    path: Path,
    *,
    design: str,
    pdk: str,
    node: str,
    agent: str,
    decision: str,
    parent: str = "",
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if expected_sha256 and sha != expected_sha256:
        raise ValueError(f"Curated source changed: {path}")
    frame = json.loads(raw)
    if frame["design_id"] != design:
        raise ValueError("Result belongs to a different design")
    if frame.get("original_flow_status") == "failed":
        decision = (
            "diagnostic measurement of failed flow; not a qualified repeat; not adopted"
        )
    result = {
        "design": design,
        "pdk": pdk,
        "node": node,
        "agent": agent,
        "parent": parent,
        "decision": decision,
        "run_id": frame["run_id"],
        "condition_id": frame["condition_id"],
        "objective_id": frame["objective_id"],
        "result_path": str(path.resolve()),
        "result_sha256": sha,
    }
    for column, (metric, scale) in FIELDS.items():
        value = frame["metrics"].get(metric)
        result[column] = float(value) * scale if value is not None else ""
    result["route_drc"] = frame.get("route_drc", "")
    result["setup_wns_ps"] = min(0, result["setup_ws_ps"])
    result["hold_wns_ps"] = min(0, result["hold_ws_ps"])
    result["same_condition_parent"] = ""
    result["parent_power_change_pct"] = ""
    result["parent_area_change_pct"] = ""
    return result


def attach_deltas(rows: list[dict[str, Any]]) -> None:
    lookup = {(x["design"], x["pdk"], x["node"]): x for x in rows}
    if len(lookup) != len(rows):
        raise ValueError("Node identities must be unique within each case")
    for row in rows:
        row["same_condition_parent"] = ""
        row["parent_power_change_pct"] = ""
        row["parent_area_change_pct"] = ""
        if not row["parent"]:
            continue
        parent = lookup.get((row["design"], row["pdk"], row["parent"]))
        if parent is None:
            raise ValueError("A parent must be an actual exported measurement")
        same = all(row[key] == parent[key] for key in ("condition_id", "objective_id"))
        row["same_condition_parent"] = same
        if same:
            for column, metric in (
                ("parent_power_change_pct", "power_mw"),
                ("parent_area_change_pct", "instance_area_um2"),
            ):
                if parent[metric] != 0:
                    row[column] = 100 * (row[metric] / parent[metric] - 1)


def recorded_finishing_parent(request: dict[str, Any]) -> str | None:
    """Use the explicit native action receipt, with its actual input identity."""
    source = request.get("source")
    if not (source and request.get("source_sha256") and request.get("parent_run_id")):
        return None
    path = Path(source)
    if hashlib.sha256(path.read_bytes()).hexdigest() != request["source_sha256"]:
        raise ValueError("Recorded finishing input changed")
    if json.loads(path.read_text())["run_id"] != request["parent_run_id"]:
        raise ValueError("Recorded finishing parent does not match its actual input")
    return source


def collect(root: Path, work: Path) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    rows, originals = [], {}
    with (root / "admin/INVITED_PAPER_METRICS_20261020.csv").open() as stream:
        for item in csv.DictReader(stream):
            path = Path(item["result_path"])
            row = measured_node(
                path,
                design=item["design"],
                pdk="asap7",
                node=item["node"],
                agent=item["agent"],
                parent=item["parent"],
                decision=item["decision"],
                expected_sha256=item["result_sha256"],
            )
            if (item["design"], item["node"]) == ("ibex", "IP3"):
                state = ibex_validation_state(
                    root / "var/business/a29-paper-delivery-20261020",
                    row["result_sha256"],
                )
                if state:
                    row["decision"] = state
            rows.append(row)
            originals[row["result_sha256"]] = path.read_bytes()
    aliases = {str(Path(x["result_path"]).resolve()): x for x in rows}
    new = []
    for pdk, runtime in (
        ("nangate45", "runtime-nangate45"),
        ("asap7", "runtime-asap7-relays"),
    ):
        state = work / runtime / "experiments"
        paths = list(state.glob("*/a30-*/result.json"))
        paths += list(state.glob("*/a30-*/native-candidates/candidates/*/result.json"))
        for path in sorted(paths):
            frame = json.loads(path.read_text())
            if not {"condition_id", "objective_id", "snapshot_ids"} <= frame.keys():
                continue
            experiment = next(p for p in path.parents if (p / "request.json").exists())
            request = json.loads((experiment / "request.json").read_text())
            design = frame["design_id"]
            suffix = (
                str(path.parent.relative_to(experiment))
                if path.parent != experiment
                else "selected"
            )
            node = experiment.name.removeprefix("a30-" + design + "-" + pdk + "-")
            if suffix != "selected":
                node += "/" + path.parent.name
            agent = request["capability"]
            mode = request.get("operation", "")
            if agent in {"dpl", "goal"} and mode == "replay":
                agent += " (qualified source replay)"
            status = experiment / "status.json"
            status_text = (
                json.loads(status.read_text()).get("status")
                if status.exists()
                else "in_progress"
            )
            row = measured_node(
                path,
                design=design,
                pdk=pdk,
                node=node,
                agent=agent,
                decision="measured; native case "
                + status_text
                + "; adoption not asserted",
            )
            # A public input receipt, not path ordering, identifies the real parent.
            receipt = experiment / "input-receipt.json"
            source = (
                json.loads(receipt.read_text()).get("source")
                if receipt.exists()
                else recorded_finishing_parent(request)
            )
            new.append((row, str(Path(source).resolve()) if source else None))
            aliases[str(path.resolve())] = row
            originals[row["result_sha256"]] = path.read_bytes()
    for row, source in new:
        if source:
            if source not in aliases:
                raise ValueError("Measured relay has an unexported parent: " + source)
            parent = aliases[source]
            if (parent["design"], parent["pdk"]) != (row["design"], row["pdk"]):
                raise ValueError("A physical handoff cannot cross design/PDK")
            row["parent"] = parent["node"]
        rows.append(row)
    attach_deltas(rows)
    return rows, originals


def export(root: Path, work: Path, output: Path) -> dict[str, Any]:
    rows, originals = collect(root, work)
    output.mkdir(parents=True, exist_ok=True)
    snapshots = output / "result-snapshots"
    snapshots.mkdir(exist_ok=True)
    for sha, content in originals.items():
        if hashlib.sha256(content).hexdigest() != sha:
            raise ValueError(
                "A source changed during collection; take a fresh snapshot"
            )
        (snapshots / (sha + ".json")).write_bytes(content)
    with (output / "relay-nodes.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (output / "relay-nodes.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    )
    cases = []
    for design in ("gcd", "ibex", "jpeg", "ariane"):
        for pdk in ("asap7", "nangate45"):
            found = [x for x in rows if (x["design"], x["pdk"]) == (design, pdk)]
            edges = [
                {
                    "parent": x["parent"],
                    "child": x["node"],
                    "same_conditions": x["same_condition_parent"],
                }
                for x in found
                if x["parent"]
            ]
            runtime = (
                "runtime-nangate45" if pdk == "nangate45" else "runtime-asap7-relays"
            )
            tasks = []
            for request in sorted(
                (work / runtime / "experiments" / design).glob("a30-*/request.json")
            ):
                task = json.loads(request.read_text())
                status = request.parent / "status.json"
                state = (
                    json.loads(status.read_text())
                    if status.exists()
                    else {"status": "no terminal receipt yet"}
                )
                tasks.append(
                    {
                        "experiment": request.parent.name,
                        "capability": task["capability"],
                        "operation": task.get("operation"),
                        "state": state,
                    }
                )
            cases.append(
                {
                    "design": design,
                    "pdk": pdk,
                    "measured_nodes": len(found),
                    "actual_edges": edges,
                    "workflow_tasks": tasks,
                    "status": "has measured records"
                    if found
                    else "waiting for first measurement",
                }
            )
    summary = {
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "cases": cases,
        "measured_nodes": len(rows),
        "result_snapshots": len(originals),
        "policy": "Actual branches only. Query is evidence/diagnosis, not a fabricated PPA improvement. Source replay is not new Student evolution. A final measurement is not automatically adoption. Empty fields are unknown. Missing cases stay visible.",
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.root, args.work, args.output), ensure_ascii=False))

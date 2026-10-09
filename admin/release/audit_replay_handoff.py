"""Independently reload both handed-off designs and check native bytes/results."""

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import time
import urllib.request

from eda_toolkits.inputs import SnapshotExecutionClient, snapshot_inputs
from eda_toolkits.jobs import native_task
from openroad_platform_client import KernelClient


SCRIPT = """file mkdir outputs
set block [ord::get_db_block]
set dbu [$block getDbUnitsPerMicron]
set sum 0.0
foreach inst [$block getInsts] {
  set master [$inst getMaster]
  set sum [expr {$sum + double([$master getWidth])*[$master getHeight]/$dbu/$dbu}]
}
puts [format "AUDIT_INSTANCE_AREA_UM2 %.12g" $sum]
puts "AUDIT_INSTANCE_COUNT [llength [$block getInsts]]"
write_verilog outputs/audit-netlist.v
foreach {check delay} {setup max hold min} {
  sta::redirect_file_begin "outputs/audit-$check.json"
  report_checks -path_delay $delay -group_path_count 200 -endpoint_path_count 1 -fields {slew cap input_pins net fanout} -format json -digits 10
  sta::redirect_file_end
}
"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--receiver", type=Path, required=True)
    parser.add_argument("--data-url", required=True)
    parser.add_argument("--kernel-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    package = json.loads(args.package.read_text())
    proposal = json.loads((args.receiver / "identity.json").read_text())["proposal"][
        "changes"
    ]
    if len(proposal) != 1:
        raise ValueError("Replay audit expects exactly one bounded resize")
    change = proposal[0]
    grant = next(
        p for p in package["buffer_permissions"] if p["instance"] == change["instance"]
    )
    if change["target_master"] not in grant["allowed_masters"]:
        raise ValueError("Resize not permitted")
    kernel = KernelClient(args.kernel_url, timeout=60)
    execution = SnapshotExecutionClient(args.kernel_url, timeout=60)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    sources, native, snapshots = [], {}, {}

    def raw(run_id, artifact):
        locator = kernel.artifact_locator(run_id, artifact["artifact_id"])
        path = Path(locator["path"])
        actual = sha(path)
        if actual != locator["sha256"] or actual != artifact["sha256"]:
            raise ValueError("Original byte identity mismatch")
        sources.append(
            {
                "endpoint": args.kernel_url,
                "locator": locator,
                "actual_sha256": actual,
                "actual_size_bytes": path.stat().st_size,
            }
        )
        return path.read_bytes()

    for role, sid in (
        ("baseline", package["scope"]["snapshot_id"]),
        ("candidate", package["handoff_id"] + "-candidate"),
    ):
        with opener.open(
            args.data_url + "/snapshots/" + sid + "/summary?detail=full", timeout=60
        ) as response:
            response_bytes = response.read()
        (args.output / (role + "-snapshot.json")).write_bytes(response_bytes)
        snapshot = json.loads(response_bytes)["data"]["snapshot"]
        snapshots[role] = snapshot
        original, staged = snapshot_inputs(snapshot)
        task = native_task(snapshot, original, staged, SCRIPT)
        task["inputs"]["native_extra_paths"] = [
            "outputs/audit-netlist.v",
            "outputs/audit-setup.json",
            "outputs/audit-hold.json",
        ]
        (args.output / (role + "-task.json")).write_text(json.dumps(task, indent=2))
        run_id = execution.submit(task)["run"]["run_id"]
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            run = execution.run(run_id)
            if run["status"] in (
                "succeeded",
                "failed",
                "timed_out",
                "cancelled",
                "lost",
            ):
                break
            time.sleep(0.2)
        result = {
            "run": run,
            "artifacts": execution.artifacts(run_id),
            "logs": execution.logs(run_id, max_bytes=65536),
            "resources": execution.resources(run_id),
        }
        (args.output / (role + "-result.json")).write_text(json.dumps(result, indent=2))
        if run["status"] != "succeeded":
            raise RuntimeError("Independent native audit did not succeed: " + run_id)

        def output(path):
            return raw(
                run_id,
                next(row for row in result["artifacts"] if row["store_key"] == path),
            )

        report = output("reports/native.rpt").decode()
        (args.output / (role + "-native.rpt")).write_text(report)
        area = float(
            next(
                line.split()[-1]
                for line in report.splitlines()
                if line.startswith("AUDIT_INSTANCE_AREA_UM2 ")
            )
        )
        native[role] = {"area_um2": area, "run_id": run_id}
        (args.output / (role + ".v")).write_bytes(output("outputs/audit-netlist.v"))
        for check in ("setup", "hold"):
            content = output("outputs/audit-" + check + ".json")
            (args.output / (role + "-" + check + ".json")).write_bytes(content)
            paths = json.loads(content)["checks"]
            worst = min(paths, key=lambda p: p["slack"])
            native[role][check] = {
                "count": len(paths),
                "worst_slack_ns": worst["slack"] * 1e9,
                "endpoint": worst["endpoint"],
                "startpoint": worst["startpoint"],
            }
    before, after = (
        (args.output / "baseline.v").read_text(),
        (args.output / "candidate.v").read_text(),
    )
    expected = before.replace(
        " " + grant["original_master"] + " " + grant["instance"] + " (",
        " " + change["target_master"] + " " + grant["instance"] + " (",
    )
    only_allowed_change = before != after and after == expected
    (args.output / "netlist.diff").write_text(
        "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True)))
    )
    fixed = {}
    for role, snapshot in snapshots.items():
        context = snapshot["run_summary"]["timing_context"]
        wanted = [context["constraints"], *context["libraries"], context["parasitics"]]
        fixed[role] = {}
        for path in wanted:
            artifact = next(
                row
                for row in snapshot["source_artifacts"]
                if row["logical_path"] == path
            )
            fixed[role][path] = hashlib.sha256(
                raw(artifact["run_id"], artifact)
            ).hexdigest()
    conditions_match = fixed["baseline"] == fixed["candidate"]
    resized, exported = (
        json.loads((args.receiver / name).read_text())
        for name in ("physical.json", "export.json")
    )
    fresh_matches = {}
    for check, suffix in (("setup", ""), ("hold", "_hold")):
        live = json.loads(
            raw(
                resized["run"]["run_id"],
                next(
                    row
                    for row in resized["artifacts"]
                    if row["store_key"] == "outputs/" + check + ".json"
                ),
            )
        )["checks"]
        fresh = json.loads(
            raw(
                exported["run"]["run_id"],
                next(
                    row
                    for row in exported["artifacts"]
                    if row["store_key"] == "query-data/timing_report" + suffix + ".json"
                ),
            )
        )["checks"]
        independent = json.loads(
            (args.output / ("candidate-" + check + ".json")).read_text()
        )["checks"]
        fresh_matches[check] = live == fresh == independent
    passed = only_allowed_change and conditions_match and all(fresh_matches.values())
    result = {
        "passed": passed,
        "kind": "Clean installed-wheel development replay; not formal model measurement",
        "package_path": str(args.package),
        "package_sha256": sha(args.package),
        "only_allowed_netlist_change": only_allowed_change,
        "change": change,
        "fixed_conditions_match": conditions_match,
        "fixed_input_hashes": fixed,
        "fresh_process_matches": fresh_matches,
        "native": native,
        "area_delta_um2": native["candidate"]["area_um2"]
        - native["baseline"]["area_um2"],
        "setup_delta_ns": native["candidate"]["setup"]["worst_slack_ns"]
        - native["baseline"]["setup"]["worst_slack_ns"],
        "repair_success": native["candidate"]["setup"]["worst_slack_ns"] >= 0
        and native["candidate"]["hold"]["worst_slack_ns"] >= 0,
        "sources": sources,
        "program_sha256": sha(Path(__file__)),
        "limits": [
            "Native report_checks samples; no exhaustive all-path or multicorner signoff",
            "Original fixed extracted parasitics; no reroute, fresh extraction or legality proof",
        ],
    }
    (args.output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "passed",
                    "change",
                    "area_delta_um2",
                    "setup_delta_ns",
                    "repair_success",
                )
            }
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Audit a completed P3 campaign; this records execution evidence, not PPA benefit."""

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import zipfile
from pathlib import Path

from accept_native_campaign import audit_model_ledger
from flow_native_baseline import FORMAL, digest, now, write_json


def read(path):
    return json.loads(path.read_text())


def retained_tasks(before, final):
    """A resumed task must retain its request, producer, and registered bytes."""
    keys = (
        "task",
        "idempotency_key",
        "input_hashes",
        "candidate_id",
        "parent_run_id",
        "run_id",
        "producer_run_id",
        "artifacts",
    )
    return all(
        name in final
        and all(final[name].get(key) == value[key] for key in keys if key in value)
        for name, value in before.items()
    )


def consumed_parameters(config, log, scope):
    """Match the executed tool command to the inherited candidate configuration."""
    parameters = {
        key: float(value)
        for key, value in re.findall(
            r"^export\s+(\w+)\s*=\s*([-+\d.eE]+)\s*$", config, re.MULTILINE
        )
    }
    names = {
        "floorplan": ("FLOORPLAN_PIN_LAYER_ADJUST", "FLOORPLAN_ABOVE_LAYER_ADJUST"),
        "routing": ("PIN_LAYER_ADJUST", "ABOVE_LAYER_ADJUST"),
        "cts": ("CTS_CLUSTER_SIZE", "CTS_CLUSTER_DIAMETER"),
    }[scope]
    expected = [parameters[name] for name in names]
    if scope == "cts":
        command = re.search(r"^clock_tree_synthesis\s+(.+)$", log, re.MULTILINE)
        matches = [
            re.search(rf"{flag}\s+([-+\d.eE]+)", command[1]) if command else None
            for flag in ("-sink_clustering_size", "-sink_clustering_max_diameter")
        ]
        actual = [float(match[1]) for match in matches if match]
    else:
        matches = re.findall(
            rf"^A2_LAYER_ADJUST scope={scope} pin=([-+\d.eE]+) above=([-+\d.eE]+)$",
            log,
            re.MULTILINE,
        )
        actual = list(map(float, matches[0])) if len(matches) == 1 else []
    return {
        "scope": scope,
        "expected": expected,
        "actual": actual,
        "matched": len(actual) == 2
        and all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(actual, expected)),
    }


def audit(run):
    receipt = read(run / "receipt.json")
    if receipt["status"] != "completed":
        raise ValueError("Wait for normal campaign completion before final acceptance.")
    flow = run / "source/flow"
    backup = flow / "backup_dir/nangate45/aes"
    manifest = read(backup / "campaign_manifest.json")
    final = read(run / "final-execution.json")
    tasks, runs = final["tasks"], final["runs"]
    checks = {
        "normal_exit": receipt.get("exit_code") == 0,
        "source_unchanged": receipt.get("source_changed") == [],
        "installed_environment_unchanged": receipt.get(
            "execution_environment_unchanged"
        )
        is True,
        "full_campaign_requested": manifest["iterations"] == 2
        and manifest["runs"] == 3
        and manifest["llm_enabled"] is True
        and manifest["predictor"] == "true",
    }
    epochs = receipt["epochs"]
    gates = ["1:1:place", "1:cts:direct_parameter_proposal", "1:2", "1:7"]
    checks["four_actual_interruption_windows"] = (
        len(epochs) == 5
        and [row["gate"] for row in epochs[:4]] == gates
        and all(
            row["status"] == "interrupted"
            and row["stopped_session"]["publishers_after"] == []
            for row in epochs[:4]
        )
        and epochs[4]["status"] == "completed"
    )
    for epoch in range(4):
        before = read(run / f"interruption-{epoch}-before.json")
        checks[f"window_{epoch}_retains_requests_runs_artifacts"] = retained_tasks(
            before["tasks"], tasks
        )
        checks[f"window_{epoch}_retains_model_events"] = all(
            row in final["ledger"] for row in before["ledger"]
        )
    submit = epochs[0]["gate_evidence"]
    initial = read(run / "interruption-0-before.json")["tasks"][
        "iteration-1/slot-1-place.json"
    ]
    checks["actual_lost_submit_reply_window"] = (
        "run_id" not in initial and initial["status"] == "prepared"
    )
    checks["original_accepted_run_recovered"] = (
        tasks["iteration-1/slot-1-place.json"]["run_id"] == submit["run_id"]
    )
    model = epochs[1]["gate_evidence"]
    response = read(run / "platform-state/model-responses" / (model["key"] + ".json"))
    replays = [
        json.loads(line)
        for line in (run / "platform-state/model-responses/replays.jsonl")
        .read_text()
        .splitlines()
    ]
    checks["original_model_response_replayed"] = (
        response["call_id"] == model["call_id"]
        and response["response_sha256"] == model["response_sha256"]
        and hashlib.sha256(
            json.dumps(
                response["response"], sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        == model["response_sha256"]
        and any(
            row["call_id"] == model["call_id"]
            and row["response_sha256"] == model["response_sha256"]
            for row in replays
        )
    )
    usage = read(backup / "llm_usage_summary.json")
    ledger = audit_model_ledger(flow, manifest, usage)
    checks["model_ledger_complete"] = ledger["complete"]
    received = [row for row in final["ledger"] if row["event"] == "response_received"]
    checks["real_model_decisions_in_both_rounds"] = len(received) >= 4 and any(
        row.get("scope") == "inter_iteration" and row.get("target_iteration") == 2
        for row in received
    )
    starts = [row for row in final["ledger"] if row["event"] == "request_started"]
    checks["paid_call_ids_not_duplicated"] = len(
        {row["call_id"] for row in starts}
    ) == len(starts)
    model_keys = [
        tuple(
            row.get(key)
            for key in (
                "iteration",
                "scope",
                "stage",
                "operation",
                "react_step",
                "request_sha256",
                "provider_hash",
            )
        )
        for row in starts
    ]
    checks["same_model_request_not_reissued"] = len(set(model_keys)) == len(model_keys)
    review_path = run / "model-decision-review.json"
    review = read(review_path) if review_path.is_file() else {}
    checks["model_decision_review_intact"] = (
        review.get("verified") is True
        and review.get("campaign_id") == manifest["campaign_id"]
        and bool(review.get("responses"))
        and bool(review.get("evidence_files"))
        and all(
            (run / entry["path"]).is_file()
            and digest(run / entry["path"]) == entry["sha256"]
            for entry in (
                *review.get("responses", []),
                *review.get("evidence_files", {}).values(),
            )
        )
    )
    identifiers = [row["run_id"] for row in runs]
    checks["registered_run_ids_unique"] = len(identifiers) == len(set(identifiers))
    run_map = {row["run_id"]: row for row in runs}
    keys = [
        tuple(
            row.get("labels", {}).get(k)
            for k in ("campaign_id", "iteration", "candidate_slot", "stage")
        )
        for row in runs
    ]
    checks["one_registered_run_per_candidate_stage"] = len(keys) == len(set(keys))
    physical, feedback = [], []
    for name, value in tasks.items():
        if value.get("stage") in {"place", "cts", "route_finish"}:
            checks[name + ":registered_status"] = (
                value["status"] == run_map[value["run_id"]]["status"]
            )
            if value["status"] != "succeeded":
                continue
            archive = next(
                row for row in value["artifacts"] if row["kind"] == "flow_archive"
            )
            path = run / "platform-state" / Path(name).with_suffix(".zip")
            checks[name + ":archive_hash"] = (
                path.is_file() and digest(path) == archive["sha256"]
            )
            with zipfile.ZipFile(path) as bundle:
                stem = {"place": "3_place", "cts": "4_cts", "route_finish": "6_final"}[
                    value["stage"]
                ]
                suffixes = (
                    ("odb", "sdc", "def", "v", "spef", "gds")
                    if value["stage"] == "route_finish"
                    else ("odb", "sdc")
                )
                checks[name + ":physical_outputs"] = all(
                    f"flow/results/{stem}.{suffix}" in bundle.namelist()
                    for suffix in suffixes
                )
            physical.append(
                {"record": name, "run_id": value["run_id"], "archive": archive}
            )
        if name.endswith("-feedback.json"):
            checks[name + ":imported_once"] = (
                value.get("imported") is True
                and value["import_receipt"]["status"] == "imported"
                and value["import_receipt"]["attempts"] == 1
            )
            snapshot = value["summary"]["snapshot"]
            checks[name + ":physical_analysis_lineage"] = (
                snapshot["run_id"] == value["physical_run_id"]
                and snapshot["producer_run_id"] == value["producer_run_id"]
            )
            sdk = (
                run / "sdk-feedback" / (Path(name).parent.name + "-" + Path(name).name)
            )
            checks[name + ":sdk_metrics_and_source"] = (
                sdk.is_file() and read(sdk).get("accepted") is True
            )
            feedback.append(
                {
                    "record": name,
                    "snapshot_id": value["snapshot_id"],
                    "sdk_receipt": str(sdk),
                }
            )
    checks["eighteen_physical_stage_tasks"] = (
        sum(
            name.endswith("-" + stage + ".json")
            for name in tasks
            for stage in ("place", "cts", "route_finish")
        )
        == 18
    )
    evaluations = [
        value
        for name, value in tasks.items()
        if not name.endswith("-feedback.json")
        and value.get("stage", "").startswith("eval_")
        and value["status"] == "succeeded"
    ]
    checks["all_successful_evaluations_imported"] = (
        len(feedback) == len(evaluations) and len(feedback) >= 8
    )
    rounds, clocks, consumption = [], [], []
    for iteration in (1, 2):
        dump = backup / f"result_dump_{iteration}"
        result = subprocess.run(
            [
                str(FORMAL / ".venv/bin/python"),
                str(flow / "driver_orchestration.py"),
                "validate-backup",
                "--directory",
                str(dump),
                "--manifest",
                str(backup / "campaign_manifest.json"),
                "--iteration",
                str(iteration),
                "--runs",
                "3",
            ],
            cwd=flow,
            capture_output=True,
            text=True,
            check=False,
        )
        checks[f"round_{iteration}_canonical_backup"] = result.returncode == 0
        metrics = read(dump / f"metrics_final_iter{iteration}.json")
        valid = [
            row
            for row in metrics
            if row.get("tns_source") == "cp0_eval"
            and all(
                isinstance(row.get(k), (int, float)) and math.isfinite(row[k])
                for k in ("TNS_EVAL", "power", "ecp", "wl")
            )
        ]
        checks[f"round_{iteration}_actual_final_measurements"] = (
            len(metrics) == 3 and len(valid) >= 2
        )
        for row in valid:
            slot = row["run_id"]
            config = dump / f"config_{slot}.mk"
            task_name = f"iteration-{iteration}/slot-{slot}-route_finish.json"
            checks[task_name + ":executed_final_config"] = (
                digest(config) == tasks[task_name]["input_hashes"]["config"]
            )
            archive = run / "platform-state" / Path(task_name).with_suffix(".zip")
            with zipfile.ZipFile(archive) as bundle:
                for scope, filename in (
                    ("floorplan", "2_1_floorplan.log"),
                    ("cts", "4_1_cts.log"),
                    ("routing", "5_1_grt.log"),
                ):
                    log = dump / f"logs_dump/aes/run_{slot}" / filename
                    raw = bundle.read("flow/logs/" + filename)
                    checks[task_name + ":" + scope + "_registered_log"] = (
                        log.read_bytes() == raw
                    )
                    observation = consumed_parameters(
                        config.read_text(), raw.decode(), scope
                    )
                    checks[task_name + ":" + scope + "_parameters_used"] = observation[
                        "matched"
                    ]
                    consumption.append(
                        {
                            **observation,
                            "iteration": iteration,
                            "slot": slot,
                            "run_id": tasks[task_name]["run_id"],
                            "config_sha256": digest(config),
                            "log_sha256": digest(log),
                            "archive_sha256": digest(archive),
                        }
                    )
        checks[f"round_{iteration}_three_input_rows"] = (
            len(
                list(csv.DictReader((dump / f"input_batch_iter{iteration}.csv").open()))
            )
            == 3
        )
        for stage in ("place", "cts"):
            decision_path = dump / f"drp_{stage}_iter{iteration}.json"
            decision = read(decision_path)
            checks[f"round_{iteration}_{stage}_trusted_clone"] = (
                decision["lineage_trusted_count"] >= 1
            )
            checks[f"round_{iteration}_{stage}_model_decision_used"] = any(
                row.get("origin") == "llm"
                for row in decision["stage_generated_provenance"]
            ) or (
                checks["model_decision_review_intact"]
                and any(
                    row.get("verified") is True
                    and row.get("iteration") == iteration
                    and row.get("stage") == stage
                    and row.get("decision_sha256") == digest(decision_path)
                    and row.get("selected_parameters")
                    == decision["stage_generated_params"]
                    for row in review.get("stage_model_decisions", [])
                )
            )
            if iteration == 2:
                checks[f"round_2_{stage}_predictor_used"] = (
                    decision["effective_rank_key"] == "promising_cost"
                    and decision["scored_count"] == 3
                    and decision["fallback_reason"] is None
                )
        clocks.append(float((dump / "cp0.txt").read_text()))
        if iteration == 2:
            batch = dump / "input_batch_iter2.csv"
            lifecycle = read(dump / "candidate_lifecycle_iter2.json")
            events = [
                row for row in lifecycle["events"] if row.get("stage") == "csv_written"
            ]
            checks["next_csv_bound_to_model_pipeline"] = len(events) == 3 and all(
                row.get("details", {}).get("csv_sha256") == digest(batch)
                for row in events
            )
            checks["review_matches_executed_next_csv"] = review.get(
                "incoming_csv_sha256"
            ) == digest(batch)
        rounds.append({"iteration": iteration, "metrics": metrics})
    checks["fixed_reference_clock"] = clocks[0] > 0 and clocks[0] == clocks[1]
    return {
        "engineering_accepted": all(checks.values()),
        "audited_at": now(),
        "campaign_id": manifest["campaign_id"],
        "checks": checks,
        "rounds": rounds,
        "physical": physical,
        "parameter_consumption": consumption,
        "model_decision_review": review,
        "feedback": feedback,
        "usage": usage,
        "model_ledger_audit": ledger,
        "model_cost_complete": ledger["cost_complete"],
        "business_acceptance": "pending owner review",
        "platform_benefit_proven": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    run = args.run_root.resolve()
    result = audit(run)
    write_json(run / "p3-acceptance.json", result)
    print(
        json.dumps(
            {
                "engineering_accepted": result["engineering_accepted"],
                "failed_checks": [
                    name for name, passed in result["checks"].items() if not passed
                ],
            }
        )
    )
    raise SystemExit(0 if result["engineering_accepted"] else 1)

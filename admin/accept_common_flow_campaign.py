"""Audit U2's actual common-tool stages and the existing full Flow contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_native_baseline import digest, now, write_json
from qualify_common_toolchain import IMAGE_SHA, OPENROAD, ORFS


def verify_identity(profile, receipt):
    identity = receipt.get("toolchain", {})
    declared = profile["toolchain"]
    if identity != {**declared, "runtime": profile["runtime"]}:
        raise ValueError("Stage did not verify the actual common tools")
    if receipt.get("profile") != profile:
        raise ValueError("Stage used a different profile")
    if (
        identity["image_sha256"],
        identity["orfs_commit"],
        identity["openroad_commit"],
    ) != (IMAGE_SHA, ORFS, OPENROAD):
        raise ValueError("Stage belongs to another toolchain")
    command = receipt["command"]
    if (
        command[0] != profile["runtime"]["executable"]
        or profile["runtime"]["image"] not in command
    ):
        raise ValueError("Stage did not execute inside the common image")
    if receipt["returncode"] != 0:
        raise ValueError("Failed physical stage cannot pass")


def audit(run):
    from accept_platform_campaign import audit as full_campaign_audit

    common = json.loads((run / "common.json").read_text())
    profile = json.loads((run / "profile.json").read_text())
    if digest(run / "profile.json") != common["profile_sha256"]:
        raise ValueError("Frozen profile changed")
    if digest(Path(profile["runtime"]["image"])) != IMAGE_SHA:
        raise ValueError("Actual image changed")
    if (
        digest(Path(profile["toolchain"]["source_manifest_path"]))
        != profile["toolchain"]["source_manifest_sha256"]
    ):
        raise ValueError("Common source provenance changed")
    qualified = Path(common["qualification_root"])
    if digest(qualified / "u1-acceptance.json") != common["qualification_sha256"]:
        raise ValueError("Qualification receipt changed")
    result = full_campaign_audit(run)
    index = json.loads((run / "stage-receipts/index.json").read_text())
    final = json.loads((run / "final-execution.json").read_text())
    expected = {
        value["run_id"]
        for name, value in final["tasks"].items()
        if not name.endswith("-feedback.json")
    }
    if len(index) != len(expected) or {row["run_id"] for row in index} != expected:
        raise ValueError("Missing actual physical or evaluation stage provenance")
    for row in index:
        path = run / row["path"]
        if digest(path) != row["artifact"]["sha256"]:
            raise ValueError("Stage receipt does not match registered bytes")
        receipt = json.loads(path.read_text())
        verify_identity(profile, receipt)
        if receipt["profile_sha256"] != common["profile_sha256"]:
            raise ValueError("Stage profile bytes changed")
    query = json.loads((run / "query-completion/receipt.json").read_text())
    result["checks"].update(
        common_stage_identities=True,
        common_image_and_source=True,
        data_check_did_not_rerun_eda=query.get("original_runs_unchanged") is True,
        compatibility_precheck=json.loads((run / "precheck/receipt.json").read_text())[
            "status"
        ]
        == "completed",
    )
    result.update(
        engineering_accepted=all(result["checks"].values()),
        slice="U2",
        audited_at=now(),
        toolchain=profile["toolchain"],
        native_flow_commit=profile["source_commit"],
        baseline_scope="this common environment campaign only",
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["audit"])
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run_root.resolve())
    write_json(args.run_root / "u2-acceptance.json", result)
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

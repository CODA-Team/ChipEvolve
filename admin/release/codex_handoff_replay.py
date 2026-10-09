"""Run a real Codex receiver against explicitly selected installed EF/DF services.

All EDA construction and validation stays in the public Query Agent receiver and
Toolkits. This replay harness proposes no task or edit on the receiver's behalf.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

from query_agent.domain.handoff import HandoffPackage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--data-url", required=True)
    parser.add_argument("--kernel-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    package_path = args.package.resolve()
    payload = package_path.read_bytes()
    package = HandoffPackage.model_validate_json(payload)
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    workspace, receiver = args.output / "workspace", args.output / "receiver"
    workspace.mkdir()
    receiver.mkdir()
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "handoff_id": {"type": "string"},
            "accepted": {"type": "boolean"},
            "physical_run_id": {"type": ["string", "null"]},
            "snapshot_id": {"type": ["string", "null"]},
            "reason": {"type": "string"},
        },
        "required": [
            "handoff_id",
            "accepted",
            "physical_run_id",
            "snapshot_id",
            "reason",
        ],
    }
    (workspace / "outcome-schema.json").write_text(json.dumps(schema))
    prefix = shlex.join(
        [
            sys.executable,
            "-I",
            "-m",
            "query_agent",
            "receive-handoff",
            "--data-url",
            args.data_url,
            "--kernel-url",
            args.kernel_url,
            "--package",
            str(package_path),
            "--package-sha256",
            hashlib.sha256(payload).hexdigest(),
            "--receiver-output",
            str(receiver),
        ]
    )
    prompt = f"""You are a real Codex ECO receiver. Consume the immutable package below.
Use only the package and the declared public receiver CLI. Do not inspect source
code, private oracles, other experiments, credentials or production services.
Select exactly one allowed buffer resize, write proposal.json in your workspace:
{{"changes":[{{"instance":"EXACT_ALLOWED_NAME","target_master":"EXACT_ALLOWED_MASTER"}}],"reason":"WHY"}}.
Actually execute this exact prefix followed by --proposal ABSOLUTE_PROPOSAL_PATH:
{prefix}
The public receiver validates identities and permissions, submits one real
candidate and a fresh-process STA/export, then imports the resulting snapshot.
Wait for it. Do not change clock/SDC/library/corner/RC or run a direct native task.
No improvement is a valid result. Receiver completion is not timing repair.
On rejection report the real error; do not guess run IDs or results.
PACKAGE:
{package.model_dump_json(indent=2)}
"""
    (args.output / "prompt.txt").write_text(prompt)
    command = [
        shutil.which("codex"),
        "exec",
        "--ignore-user-config",
        "--ephemeral",
        "--skip-git-repo-check",
        "-C",
        str(workspace),
        "-s",
        "workspace-write",
        "--add-dir",
        str(receiver),
        "-m",
        "gpt-6.1-sol",
        "-c",
        'model_reasoning_effort="medium"',
        "-c",
        'approval_policy="never"',
        "-c",
        "sandbox_workspace_write.network_access=true",
        "--json",
        "--output-schema",
        str(workspace / "outcome-schema.json"),
        "--output-last-message",
        str(args.output / "model-outcome.json"),
        "-",
    ]
    (args.output / "invocation.json").write_text(json.dumps(command, indent=2))
    start, timed_out = time.monotonic(), False
    with (
        (args.output / "events.jsonl").open("w") as events,
        (args.output / "stderr.txt").open("w") as errors,
    ):
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=events,
            stderr=errors,
            text=True,
            start_new_session=True,
        )
        try:
            process.communicate(prompt, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    actions, usage = [], {}
    for line in (args.output / "events.jsonl").read_text().splitlines():
        event = json.loads(line)
        if event.get("type") == "turn.completed":
            usage = event.get("usage", {})
        if (
            event.get("type") == "item.completed"
            and event.get("item", {}).get("type") == "command_execution"
        ):
            actions.append(event["item"])
    receipt_path = receiver / "receipt.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else None
    invoked = any(
        "receive-handoff" in row["command"] and row.get("exit_code") == 0
        for row in actions
    )
    passed = bool(receipt) and invoked and not timed_out and process.returncode == 0
    result = {
        "handoff_id": package.handoff_id,
        "actual_receiver_completed": passed,
        "receiver": receipt,
        "data_url": args.data_url,
        "kernel_url": args.kernel_url,
        "python": sys.executable,
        "package_sha256": hashlib.sha256(payload).hexdigest(),
        "model": "gpt-6.1-sol",
        "effort": "medium",
        "usage": usage,
        "seconds": time.monotonic() - start,
        "timed_out": timed_out,
        "exit_code": process.returncode,
        "command_actions": actions,
        "cash_cost_usd": None,
        "billing": "Codex subscription",
        "program_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "outcome": "Awaiting independent result review; execution is not improvement success",
    }
    (args.output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "handoff_id",
                    "actual_receiver_completed",
                    "seconds",
                    "timed_out",
                )
            }
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

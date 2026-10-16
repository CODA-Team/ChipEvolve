"""Close an explicitly finished native batch through the public EF client.

Interrupting a resumable frontend is deliberately not a batch-close event.
The controller calls this only after its original run_stage timeout returns.
"""

import argparse
import json
import os
from pathlib import Path

from openroad_platform_client import KernelClient

from platform_execution import TERMINAL, write_record


def finalize(
    client, state, campaign, iteration, platform, design, stage, native_exit_code
):
    """Request cancellation of this closed batch's remaining work, once.

    Completion means EF acknowledged cancellation; running attempts stop through
    EF's existing cancellation lifecycle, not by killing shared process groups.
    Original leaf records remain unchanged as evidence of the native outcome.
    """
    state = Path(state)
    scope = {
        "campaign_id": campaign,
        "iteration": iteration,
        "platform": platform,
        "design": design,
        "stage": stage,
        "native_exit_code": native_exit_code,
    }
    receipt_path = state / f"iteration-{iteration}/finalize-{stage}.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if any(receipt.get(key) != value for key, value in scope.items()):
            raise ValueError("Closed batch ownership or native outcome changed.")
        if receipt["status"] == "completed":
            return receipt

    observations = []
    # Validate the full pending set before cancelling anything. Never recover a
    # missing submit reply by submitting again merely to perform cancellation.
    paths = sorted(state.glob(f"iteration-{iteration}/slot-*-{stage}.json"))
    for path in paths:
        record = json.loads(path.read_text())
        if any(
            record.get(key) != value
            for key, value in scope.items()
            if key != "native_exit_code"
        ):
            raise ValueError("Local batch ownership mismatch: " + str(path))
        if record["status"] in TERMINAL:
            continue
        if not record.get("run_id"):
            raise ValueError("Closed batch has unresolved submission: " + str(path))
        run = client.run(record["run_id"])
        labels = {
            "campaign_id": campaign,
            "iteration": str(iteration),
            "stage": stage,
            "candidate_slot": str(record["candidate_slot"]),
        }
        if (
            run["run_id"] != record["run_id"]
            or run.get("project_id") != "a2-flow"
            or run.get("design_id") != design
            or any(
                run.get("labels", {}).get(key) != value for key, value in labels.items()
            )
        ):
            raise ValueError("Remote batch ownership mismatch: " + str(path))
        observations.append(
            {"run_id": run["run_id"], "status": run["status"], "record_path": str(path)}
        )

    receipt = {**scope, "status": "closing", "observations": observations}
    write_record(receipt_path, receipt)
    for observation in observations:
        if observation["status"] not in TERMINAL | {"cancel_requested"}:
            response = client.cancel(observation["run_id"])
            observation["status"] = response["run"]["status"]
            observation["cancellation_acknowledged"] = True
            write_record(receipt_path, receipt)
    receipt["status"] = "completed"
    receipt["awaiting_terminal_run_ids"] = [
        row["run_id"] for row in observations if row["status"] not in TERMINAL
    ]
    write_record(receipt_path, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform")
    parser.add_argument("design")
    parser.add_argument("iteration", type=int)
    parser.add_argument("stage", choices=["place", "cts", "route_finish"])
    parser.add_argument("native_exit_code", type=int)
    args = parser.parse_args()
    settings = json.loads(Path(os.environ["DRP_PLATFORM_CONFIG"]).read_text())
    receipt = finalize(
        KernelClient(settings["kernel_url"], timeout=60),
        settings["state_root"],
        os.environ["DRP_CAMPAIGN_ID"],
        args.iteration,
        args.platform,
        args.design,
        args.stage,
        args.native_exit_code,
    )
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()

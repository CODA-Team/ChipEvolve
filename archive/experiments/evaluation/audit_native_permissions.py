"""Flag model-requested input mutations under the frozen investigation policy.

This reads recorded requests only. It never executes Tcl, claims that a regex is
a security boundary, or changes the frozen runner. Flags need semantic review.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from score_formal import load_state


MUTATION = re.compile(
    r"\b(?:exec|socket|load|source|read_\w+|write_\w+|resize_cell|swapMaster|"
    r"create_clock|set_clock\w*|set_output_delay|set_input_delay|set_wire_rc|"
    r"set_operating_conditions|set_timing_derate|remove_\w+|delete_\w+)\b"
)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def requested_operations(state, arm):
    if arm in ("D", "E"):
        for index, row in enumerate(state.get("operations", [])):
            yield (
                index,
                row.get("kind"),
                row.get("request", {}),
                row.get("status"),
                row.get("run_id"),
            )
    else:
        for index, row in enumerate(state.get("evidence", [])):
            yield (
                index,
                row.get("operation", {}).get("kind"),
                row.get("operation", {}),
                row.get("status"),
                None,
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--formal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Audit outputs are immutable; choose another version")
    records = []
    for receipt_path in sorted((args.formal / "receipts").glob("*.json")):
        receipt = json.loads(receipt_path.read_text())
        folder = Path(receipt["folder"])
        state = load_state(folder, receipt["arm"]) or {}
        for index, kind, operation, status, run_id in requested_operations(
            state, receipt["arm"]
        ):
            if kind not in ("native", "analysis"):
                continue
            options_error = None
            try:
                options = json.loads(operation.get("options_json") or "{}")
                if not isinstance(options, dict):
                    raise ValueError("options_json must contain an object")
            except (ValueError, TypeError) as error:
                options = {}
                options_error = str(error)
            parameters = {
                row["name"]: row["value"] for row in operation.get("parameters", [])
            }
            script = (
                operation.get("script")
                or options.get("script")
                or parameters.get("script")
            )
            alternate = {
                name: options[name]
                for name in ("extra_files", "odb_file")
                if options.get(name)
            }
            words = (
                sorted(set(MUTATION.findall(script))) if isinstance(script, str) else []
            )
            if words or alternate or options_error:
                payload = json.dumps(operation, sort_keys=True, ensure_ascii=False)
                records.append(
                    {
                        "episode_id": receipt["episode_id"],
                        "folder": str(folder),
                        "receipt_path": str(receipt_path),
                        "receipt_sha256": digest(receipt_path),
                        "operation_index": index,
                        "operation": operation,
                        "operation_sha256": hashlib.sha256(
                            payload.encode()
                        ).hexdigest(),
                        "recorded_status": status,
                        "run_id": run_id,
                        "mutation_or_external_commands": words,
                        "alternate_inputs": alternate,
                        "options_parse_error": options_error,
                        "review_status": "requires_review",
                    }
                )
    result = {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "program_sha256": digest(Path(__file__)),
        "recorded_episode_count": len(list((args.formal / "receipts").glob("*.json"))),
        "flagged_operation_count": len(records),
        "flagged_episodes": dict(Counter(row["episode_id"] for row in records)),
        "records": records,
        "limits": "Recorded model requests only, excluding adapter input-loader Tcl. Flags are conservative review prompts, not proof of execution or an exhaustive sandbox/security audit. Original inputs and actual results must be checked separately.",
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "recorded_episode_count",
                    "flagged_operation_count",
                    "flagged_episodes",
                )
            }
        )
    )


if __name__ == "__main__":
    main()

"""Check clean installed-model traces against persisted bytes and native sources.

These are development replay audits, separate from the frozen 528 measurements.
Semantic judgments are supplied in a separate signed-by-hash review record.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from openroad_platform_client import KernelClient

from audit_formal_sources import collect_refs, saved_page_check


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def pointer(value, location):
    for token in location[1:].split("/") if location else []:
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-root", type=Path, required=True)
    parser.add_argument("--sprint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", default=[])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    cache = {}
    records = []
    clients = {
        "clean": KernelClient("http://127.0.0.1:19700", timeout=60),
        "handoff": KernelClient("http://127.0.0.1:18700", timeout=60),
    }
    for name in (
        "sta-recovery-1",
        "clock-investigation-codex-1",
        "clock-investigation-codex-2",
        "handoff-result-review-codex-1",
        "handoff-result-review-codex-2",
        *args.case,
    ):
        folder = args.clean_root / name
        states = list((folder / "investigations").glob("*/state.json"))
        if len(states) != 1:
            raise ValueError("Expected one replay state: " + name)
        state_path = states[0]
        state = json.loads(state_path.read_text())
        known = {e["evidence_id"]: e for e in state["evidence"]}
        evidence_checks, fragment_checks, source_checks = [], [], []
        refs = {}
        for identity, evidence in known.items():
            content = evidence.get("content") or {}
            if "original_evidence_id" in content:
                evidence_checks.append(saved_page_check(evidence, known, folder))
            else:
                expected = evidence.get("provenance", {}).get("source_hash")
                if expected:
                    path = folder / "evidence" / (identity + ".json")
                    actual = digest(path) if path.is_file() else None
                    evidence_checks.append(
                        {
                            "evidence_id": identity,
                            "path": str(path),
                            "sha256": actual,
                            "passed": actual == expected
                            and json.loads(path.read_text()) == content,
                        }
                    )
            collect_refs(evidence, refs)
        client = clients["handoff" if name.startswith("handoff") else "clean"]
        for (run_id, artifact_id), expected in sorted(refs.items()):
            key = run_id + "/" + artifact_id
            if key not in cache:
                locator = client.artifact_locator(run_id, artifact_id)
                path = Path(locator["path"])
                cache[key] = {
                    "endpoint": client.base_url,
                    "locator": locator,
                    "actual_sha256": digest(path),
                    "actual_size_bytes": path.stat().st_size,
                }
            row = cache[key]
            passed = (
                len(expected) == 1
                and next(iter(expected))
                == row["actual_sha256"]
                == row["locator"]["sha256"]
                and row["actual_size_bytes"] == row["locator"]["size_bytes"]
            )
            source_checks.append({"key": key, "passed": passed})
        for evidence in known.values():
            for fragment in walk(evidence.get("content")):
                if not all(
                    k in fragment
                    for k in ("fragment_path", "fragment", "run_id", "artifact_id")
                ):
                    continue
                key = fragment["run_id"] + "/" + fragment["artifact_id"]
                raw = json.loads(Path(cache[key]["locator"]["path"]).read_text())
                selected = pointer(raw, fragment["fragment_path"])
                reported = fragment["fragment"]
                passed = (
                    all(selected[k] == v for k, v in reported.items())
                    if isinstance(reported, dict)
                    else selected == reported
                )
                fragment_checks.append(
                    {
                        "evidence_id": evidence["evidence_id"],
                        "source": key,
                        "pointer": fragment["fragment_path"],
                        "passed": passed,
                    }
                )
        citations = [
            {
                "claim_index": i,
                "kind": claim["kind"],
                "passed": bool(claim["evidence_ids"])
                and all(eid in known for eid in claim["evidence_ids"]),
            }
            for i, claim in enumerate((state.get("answer") or {}).get("claims", []))
            if claim["kind"] in ("fact", "comparison", "causal")
        ]
        records.append(
            {
                "case": name,
                "state_path": str(state_path),
                "state_sha256": digest(state_path),
                "status": state["status"],
                "active_seconds": state["active_seconds"],
                "budget": state["budget"],
                "outcome": (state.get("answer") or {}).get("outcome"),
                "evidence_checks": evidence_checks,
                "registered_original_checks": source_checks,
                "fragment_checks": fragment_checks,
                "citation_checks": citations,
                "source_gate_passed": all(
                    row["passed"]
                    for row in evidence_checks
                    + source_checks
                    + fragment_checks
                    + citations
                ),
                "answer_present": state.get("answer") is not None,
            }
        )
    native = {}
    for alias in ("e00", "e01"):
        native[alias] = {}
        for check in ("setup", "hold"):
            path = args.clean_root / "clock-pair-1/private" / alias / (check + ".json")
            paths = json.loads(path.read_text())["checks"]
            worst = min(paths, key=lambda row: row["slack"])
            native[alias][check] = {
                "source": str(path),
                "sha256": digest(path),
                "path_count": len(paths),
                "worst": {
                    key: worst[key]
                    for key in (
                        "startpoint",
                        "endpoint",
                        "slack",
                        "data_arrival_time",
                        "required_time",
                    )
                },
            }
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "records": records,
        "clock_independent_native_reference": native,
        "handoff_independent_native_reference": {
            "path": str(
                args.sprint / "handoff-action-independent-audit-3/summary.json"
            ),
            "sha256": digest(
                args.sprint / "handoff-action-independent-audit-3/summary.json"
            ),
        },
        "program_sha256": digest(Path(__file__)),
        "semantic_support": "Requires separate claim-by-claim reviewer record; hashes and matching fragments alone do not certify an answer.",
        "formal_measurements_modified": False,
    }
    (args.output / "records.json").write_text(json.dumps(result, indent=2) + "\n")
    (args.output / "original-locators.json").write_text(
        json.dumps(cache, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "source_gates": {
                    row["case"]: row["source_gate_passed"] for row in records
                },
                "originals": len(cache),
            }
        )
    )


if __name__ == "__main__":
    main()

"""Retrieve registered original locators and verify citation/evidence digests.

The archive execution endpoint is read-only. No native analysis is submitted.
Hash checks establish byte identity, not semantic support or causal attribution.
"""

import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

from openroad_platform_client import KernelClient, KernelError
from score_formal import load_state


_hash_stats = {"files_hashed": 0, "bytes_hashed": 0}


def file_digest(path):
    path = path.resolve()
    before = path.stat()
    with path.open("rb") as stream:
        result = hashlib.file_digest(stream, "sha256").hexdigest()
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise OSError("source changed while hashing: " + str(path))
    _hash_stats["files_hashed"] += 1
    _hash_stats["bytes_hashed"] += before.st_size
    return result


def collect_refs(value, refs):
    if isinstance(value, dict):
        if all(
            isinstance(value.get(k), str) for k in ("run_id", "artifact_id", "sha256")
        ):
            refs.setdefault((value["run_id"], value["artifact_id"]), set()).add(
                value["sha256"]
            )
        for child in value.values():
            collect_refs(child, refs)
    elif isinstance(value, list):
        for child in value:
            collect_refs(child, refs)


def saved_page_check(evidence, known, folder, visited=()):
    """Validate persisted excerpts against saved originals, without product code."""
    identity = evidence["evidence_id"]
    result = {
        "kind": "saved_evidence_page",
        "evidence_id": identity,
        "storage": "investigation state content",
        "passed": False,
    }
    try:
        if identity in visited:
            raise ValueError("cyclic saved evidence ancestry")
        page = evidence["content"]
        original = known[page["original_evidence_id"]]
        if evidence.get("scope") != original.get("scope"):
            raise ValueError("excerpt scope differs from original")
        if evidence.get("provenance", {}).get("source_hash") != original.get(
            "provenance", {}
        ).get("source_hash"):
            raise ValueError("excerpt source identity differs from original")
        source_content = original["content"]
        if (
            isinstance(source_content, dict)
            and "original_evidence_id" in source_content
        ):
            parent = saved_page_check(original, known, folder, (*visited, identity))
            if not parent["passed"]:
                raise ValueError(
                    "invalid parent excerpt: " + parent.get("error", "unknown")
                )
            result["parent_check"] = parent
        else:
            source_path = folder / "evidence" / (original["evidence_id"] + ".json")
            expected = original.get("provenance", {}).get("source_hash")
            if not expected or file_digest(source_path) != expected:
                raise ValueError("original saved response digest mismatch")
            if json.loads(source_path.read_text()) != source_content:
                raise ValueError("state original content differs from saved response")
            result["original_file"] = {"path": str(source_path), "sha256": expected}
        selected = source_content
        pointer = page["pointer"]
        if not isinstance(pointer, str) or pointer and not pointer.startswith("/"):
            raise ValueError("invalid RFC6901 pointer")
        for token in pointer[1:].split("/") if pointer else []:
            token = token.replace("~1", "/").replace("~0", "~")
            if isinstance(selected, list):
                if not token.isdecimal() or str(int(token)) != token:
                    raise ValueError("noncanonical array index")
                selected = selected[int(token)]
            elif isinstance(selected, dict):
                selected = selected[token]
            else:
                raise ValueError("pointer traverses scalar")
        full_text = json.dumps(selected, ensure_ascii=False)
        offset, text = page["offset"], page["text"]
        if (
            type(offset) is not int
            or offset < 0
            or not isinstance(text, str)
            or len(text) > 12000
        ):
            raise ValueError("invalid excerpt range")
        if offset < len(full_text) and not text:
            raise ValueError("empty excerpt inside nonempty source")
        end = min(len(full_text), offset + len(text))
        expected_next = end if end < len(full_text) else None
        checks = {
            "text_matches": text == full_text[offset : offset + len(text)],
            "full_selection_sha256": page["sha256"]
            == hashlib.sha256(full_text.encode()).hexdigest(),
            "total_characters": page["total_characters"] == len(full_text),
            "next_offset": page["next_offset"] == expected_next,
            "complete": page["complete"] is (offset == 0 and end == len(full_text)),
        }
        result.update(
            pointer=pointer,
            offset=offset,
            excerpt_characters=len(text),
            complete=page["complete"],
            checks=checks,
            passed=all(checks.values()),
        )
    except (KeyError, IndexError, TypeError, ValueError, OSError) as error:
        result["error"] = str(error)
    return result


def direct_checks(evidence, config):
    """Verify the strong baseline's file/index/native receipts on their own terms."""
    stored = evidence.get("operation", {})
    operation = {
        key: value
        for key, value in stored.items()
        if key not in ("parameters", "options_json")
    }
    operation.update(
        {row["name"]: row["value"] for row in stored.get("parameters", [])}
    )
    operation.update(json.loads(stored.get("options_json") or "{}"))
    response = evidence.get("response", {})
    checks = []
    baseline = Path(config["baseline_root"])
    if operation.get("kind") == "file" and response.get("sha256"):
        snapshot = operation.get("snapshot_id")
        if not isinstance(snapshot, str):
            return [
                {
                    "kind": "raw_file",
                    "passed": False,
                    "reason": "missing effective snapshot identity",
                }
            ]
        path = (baseline / snapshot / response["path"]).resolve()
        allowed = (
            snapshot in config["snapshots"]
            and (baseline / snapshot).resolve() in path.parents
        )
        checks.append(
            {
                "kind": "raw_file",
                "path": str(path),
                "expected": response["sha256"],
                "passed": allowed
                and path.is_file()
                and file_digest(path) == response["sha256"],
            }
        )
    for index in response.get("source_indices", []):
        path = baseline / index["snapshot_id"] / "index.sqlite"
        checks.append(
            {
                "kind": "native_index",
                "path": str(path),
                "expected": index["sha256"],
                "passed": index["snapshot_id"] in config["snapshots"]
                and path.is_file()
                and file_digest(path) == index["sha256"],
            }
        )
    if response.get("native_config_sha256"):
        path = baseline / response["snapshot_id"] / "native.json"
        checks.append(
            {
                "kind": "fixed_native_input_manifest",
                "path": str(path),
                "expected": response["native_config_sha256"],
                "passed": response["snapshot_id"] in config["snapshots"]
                and path.is_file()
                and file_digest(path) == response["native_config_sha256"],
            }
        )
        output = Path(response["source"])
        folder = Path(config["_episode_folder"]) / "native"
        checks.append(
            {
                "kind": "actual_native_output",
                "path": str(output),
                "expected": response["sha256"],
                "passed": folder.resolve() in output.resolve().parents
                and output.is_file()
                and file_digest(output) == response["sha256"],
            }
        )
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--formal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kernel-url", default="http://127.0.0.1:18700")
    parser.add_argument("--archive-kernel-url", default="http://127.0.0.1:8700")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    clients = [
        KernelClient(url, timeout=15)
        for url in (args.kernel_url, args.archive_kernel_url)
    ]
    cache_path = args.output / "original-locators.json"
    cache = json.loads(cache_path.read_text()) if cache_path.is_file() else {}
    refreshed = set()
    records = []
    for path in sorted((args.formal / "receipts").glob("*.json")):
        receipt = json.loads(path.read_text())
        folder = Path(receipt["folder"])
        state = load_state(folder, receipt["arm"])
        if state is None:
            records.append({"episode_id": receipt["episode_id"], "status": "no_state"})
            continue
        known = {row["evidence_id"]: row for row in state.get("evidence", [])}
        answer = state.get("answer") or {}
        critical = [
            row
            for row in answer.get("claims", [])
            if row["kind"] in ("fact", "comparison", "causal")
        ]
        citations = [
            {
                "text": row["text"],
                "ids": row.get("evidence_ids", []),
                "passed": bool(row.get("evidence_ids"))
                and all(eid in known for eid in row["evidence_ids"]),
            }
            for row in critical
        ]
        evidence_checks = []
        direct_source_checks = []
        config = (
            json.loads((folder / "config.json").read_text())
            if (folder / "config.json").is_file()
            else {}
        )
        config["_episode_folder"] = str(folder)
        refs = {}
        for eid, evidence in known.items():
            content = evidence.get("content")
            if (
                receipt["arm"] in ("D", "E")
                and isinstance(content, dict)
                and "original_evidence_id" in content
            ):
                evidence_checks.append(saved_page_check(evidence, known, folder))
                collect_refs(evidence, refs)
                continue
            if receipt["arm"] in ("D", "E"):
                raw_path = folder / "evidence" / (eid + ".json")
                expected = evidence.get("provenance", {}).get("source_hash")
            else:
                raw_path = folder / "evidence" / (eid + ".json")
                expected = evidence.get("sha256")
            # Failed operations can have no returned bytes; do not manufacture a hash.
            if expected:
                actual = file_digest(raw_path) if raw_path.is_file() else None
                evidence_checks.append(
                    {
                        "evidence_id": eid,
                        "path": str(raw_path),
                        "expected": expected,
                        "actual": actual,
                        "passed": actual == expected,
                    }
                )
            collect_refs(evidence, refs)
            if receipt["arm"] in ("A", "B"):
                direct_source_checks.extend(direct_checks(evidence, config))
        original_checks = []
        for (run_id, artifact_id), expected in sorted(refs.items()):
            key = run_id + "/" + artifact_id
            if key not in cache:
                errors = []
                for client in clients:
                    try:
                        locator = client.artifact_locator(run_id, artifact_id)
                        native_path = Path(locator["path"])
                        cache[key] = {
                            "endpoint": client.base_url,
                            "locator": locator,
                            "actual_sha256": file_digest(native_path),
                            "actual_size_bytes": native_path.stat().st_size,
                        }
                        break
                    except (KernelError, OSError, KeyError) as error:
                        errors.append(
                            {"endpoint": client.base_url, "error": str(error)}
                        )
                else:
                    cache[key] = {"errors": errors}
                cache_path.write_text(json.dumps(cache, indent=2) + "\n")
            native = cache[key]
            if key not in refreshed and "locator" in native:
                native_path = Path(native["locator"]["path"])
                try:
                    native["actual_sha256"] = file_digest(native_path)
                    native["actual_size_bytes"] = native_path.stat().st_size
                    native["checked_at"] = datetime.now(timezone.utc).isoformat()
                except OSError as error:
                    native.pop("actual_sha256", None)
                    native.pop("actual_size_bytes", None)
                    native["rehash_error"] = str(error)
                refreshed.add(key)
            passed = len(expected) == 1 and native.get("actual_sha256") == native.get(
                "locator", {}
            ).get("sha256") == next(iter(expected))
            passed &= (
                native.get("actual_size_bytes")
                == native.get("locator", {}).get("size_bytes")
                if "locator" in native
                else False
            )
            original_checks.append(
                {
                    "run_id": run_id,
                    "artifact_id": artifact_id,
                    "expected": sorted(expected),
                    "passed": passed,
                    "registered_original": native,
                }
            )
        records.append(
            {
                "episode_id": receipt["episode_id"],
                "folder": str(folder),
                "state_status": state["status"],
                "critical_citations": citations,
                "saved_evidence_digests": evidence_checks,
                "registered_originals": original_checks,
                "direct_source_checks": direct_source_checks,
                "citation_ids_passed": all(row["passed"] for row in citations),
                "saved_evidence_passed": all(row["passed"] for row in evidence_checks),
                "registered_originals_passed": all(
                    row["passed"] for row in original_checks
                ),
                "direct_sources_passed": all(
                    row["passed"] for row in direct_source_checks
                ),
                "registered_original_count": len(original_checks),
                "semantic_support": "separate review required; byte identity does not establish support",
            }
        )
    cache_path.write_text(json.dumps(cache, indent=2) + "\n")
    (args.output / "records.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n"
    )
    summary = {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "recorded_episodes": len(records),
        "no_state_episodes": sum(row.get("status") == "no_state" for row in records),
        "unique_originals": len(cache),
        "direct_source_check_count": sum(
            len(row.get("direct_source_checks", [])) for row in records
        ),
        "registered_original_check_count": sum(
            len(row.get("registered_originals", [])) for row in records
        ),
        "failed_original_checks": sum(
            not row["passed"]
            for rec in records
            for row in rec.get("registered_originals", [])
        ),
        "failed_evidence_digests": sum(
            not row["passed"]
            for rec in records
            for row in rec.get("saved_evidence_digests", [])
        ),
        "failed_direct_sources": sum(
            not row["passed"]
            for rec in records
            for row in rec.get("direct_source_checks", [])
        ),
        "failed_citation_ids": sum(
            not row["passed"]
            for rec in records
            for row in rec.get("critical_citations", [])
        ),
        "archive_actions": "GET artifact locator only; no submission/cancellation/restart",
        "hash_cache_policy": "No digest cache. Each requested check reads current bytes; same-size changes with indistinguishable timestamp ticks cannot be hidden by metadata reuse.",
        "hash_statistics": _hash_stats,
        "source_auditor_sha256": file_digest(Path(__file__)),
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()

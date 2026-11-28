"""Aggregate frozen grades and independent diagnosis reviews by model/arm.

This program never runs or changes a model. The fixed denominator is retained;
unknown costs, missing reviews and incomplete measurements prevent effect claims.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


REQUIRED_CHECKS = {
    "fixed_scope",
    "numeric_objects",
    "critical_sources",
    "causal_uncertainty",
    "case_success_conditions",
    "allowed_actions",
    "deadline",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_review_binding(record, review):
    """Reject judgments detached from their recorded prediction and evidence."""
    identity = record["episode_id"]
    answer_sha = hashlib.sha256(
        json.dumps(record.get("answer"), ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    if review.get("answer_sha256") != answer_sha:
        raise ValueError("Reviewed answer changed: " + identity)
    dossier_ref = review["dossier"]
    dossier_path = Path(dossier_ref["path"])
    if digest(dossier_path) != dossier_ref["sha256"]:
        raise ValueError("Reviewed dossier changed: " + identity)
    dossier = json.loads(dossier_path.read_text())
    matches = [row for row in dossier["episodes"] if row["episode_id"] == identity]
    if len(matches) != 1 or "receipt" not in matches[0]:
        raise ValueError("Review lacks its measured episode: " + identity)
    if (
        Path(matches[0]["receipt"]["folder"]).resolve()
        != Path(record["folder"]).resolve()
    ):
        raise ValueError("Review points to a different prediction folder: " + identity)
    references = review.get("critical_evidence_files", [])
    if review.get("state_file"):
        folder = Path(record["folder"])
        state_paths = (
            list((folder / "investigations").glob("*/state.json"))
            if record["arm"] in ("D", "E")
            else [folder / "state.json"]
        )
        if (
            len(state_paths) != 1
            or Path(review["state_file"]["path"]).resolve() != state_paths[0].resolve()
        ):
            raise ValueError("Review points to a different saved state: " + identity)
        references = [*references, review["state_file"]]
    if review.get("cli_result"):
        references = [*references, review["cli_result"]]
    for ref in references:
        if digest(Path(ref["path"])) != ref["sha256"]:
            raise ValueError(
                "Reviewed evidence changed: " + identity + " " + ref["path"]
            )


def episode_cost(record):
    paid, unknown = 0.0, False
    tokens = defaultdict(int)
    for receipt in record.get("model_receipts", []):
        family = receipt.get("trace_family")
        if receipt.get("receipt_missing"):
            unknown = True
            continue
        cost = receipt.get("actual_usd")
        cost = receipt.get("quoted_usage_usd") if cost is None else cost
        if cost is not None:
            paid += cost
        elif record["model"] == "deepseek-flash" or family == "judgment-traces":
            unknown = True
        usage = receipt.get("usage") or {}
        incoming = usage.get("input_tokens", usage.get("prompt_tokens"))
        outgoing = usage.get("output_tokens", usage.get("completion_tokens"))
        cached = usage.get(
            "cached_input_tokens",
            usage.get(
                "prompt_cache_hit_tokens",
                usage.get("prompt_tokens_details", {}).get("cached_tokens"),
            ),
        )
        for key, value in (
            ("input_tokens", incoming),
            ("output_tokens", outgoing),
            ("cached_input_tokens", cached),
        ):
            if isinstance(value, int):
                tokens[key] += value
    return {
        "confirmed_token_quote_usd": paid,
        "unknown_usage_or_cost": unknown,
        "recorded_tokens": dict(tokens),
        "subscription_cash_cost_usd": None
        if record["model"] == "codex"
        else "not_applicable",
    }


def primary_episode(row):
    return row["kind"] == "diagnosis" and row["repeat"] == 0 and row["ablation"] is None


def selected_direct_comparison(records):
    """Compare A with B/C on the exact preselected facts, never different sets."""
    results = []
    for model in ("codex", "deepseek-flash"):
        facts = [
            row for row in records if row["kind"] == "fact" and row["model"] == model
        ]
        selected = {row["case_id"] for row in facts if row["arm"] == "A"}
        if len(selected) != 12:
            raise ValueError("The frozen A subset must contain exactly 12 facts")
        paired = []
        for case_id in sorted(selected):
            sides = {
                row["arm"]: row
                for row in facts
                if row["case_id"] == case_id and row["arm"] in ("A", "B", "C")
            }
            if set(sides) != {"A", "B", "C"}:
                raise ValueError("Selected A fact lacks its matching B/C rows")
            paired.append(
                {
                    "case_id": case_id,
                    "arms": {
                        arm: {
                            "episode_id": row["episode_id"],
                            "grade": row["grade"],
                            "wall_seconds_used": row.get("wall_seconds_used"),
                            "cost": row["cost"],
                        }
                        for arm, row in sides.items()
                    },
                }
            )
        groups = []
        for arm in ("A", "B", "C"):
            rows = [
                row for row in facts if row["arm"] == arm and row["case_id"] in selected
            ]
            groups.append(
                {
                    "arm": arm,
                    "denominator": 12,
                    "passed": sum(row["grade"] == "passed" for row in rows),
                    "grades": dict(Counter(row["grade"] for row in rows)),
                    "wall_seconds_total": sum(
                        row.get("wall_seconds_used") or 0 for row in rows
                    ),
                    "confirmed_token_quote_usd": sum(
                        row["cost"]["confirmed_token_quote_usd"] for row in rows
                    ),
                    "episodes_with_unknown_usage_or_cost": sum(
                        row["cost"]["unknown_usage_or_cost"] for row in rows
                    ),
                }
            )
        results.append(
            {
                "model": model,
                "groups": groups,
                "paired_cases": paired,
                "limit": "Preselected 12 facts only; cannot compare this completion fraction with all 72 B/C facts.",
            }
        )
    return results


def effect_for(model, groups, rows):
    def arm(name):
        return [
            row
            for row in rows
            if primary_episode(row) and row["model"] == model and row["arm"] == name
        ]

    c, d, e = arm("C"), arm("D"), arm("E")
    complete = all(
        len(values) == 18
        and all(row["grade"] in ("passed", "failed") for row in values)
        for values in (c, d)
    )
    c_pass, d_pass, e_pass = (
        sum(row["grade"] == "passed" for row in values) for values in (c, d, e)
    )
    c_errors, d_errors, e_errors = (
        sum(row.get("critical_error") is True for row in values) for values in (c, d, e)
    )
    time_c = sum(row.get("wall_seconds_used") or 0 for row in c)
    time_d = sum(row.get("wall_seconds_used") or 0 for row in d)
    time_e = sum(row.get("wall_seconds_used") or 0 for row in e)
    time_gain = 1 - time_d / time_c if time_c else None
    cost_c = sum(row["cost"]["confirmed_token_quote_usd"] for row in c)
    cost_d = sum(row["cost"]["confirmed_token_quote_usd"] for row in d)
    cost_e = sum(row["cost"]["confirmed_token_quote_usd"] for row in e)
    unknown = any(row["cost"]["unknown_usage_or_cost"] for row in c + d)
    cost_gain = (
        1 - cost_d / cost_c if cost_c and not unknown and model != "codex" else None
    )
    actual_attempts = all(
        row.get("model_receipts") or row.get("clarification_returned") for row in c + d
    )
    quality = d_pass >= c_pass and d_errors <= c_errors
    effect = (
        complete
        and actual_attempts
        and quality
        and (
            d_pass - c_pass >= 2
            or (time_gain is not None and time_gain >= 0.2)
            or (cost_gain is not None and cost_gain >= 0.2)
        )
    )
    e_complete = len(e) == 18 and all(row["grade"] in ("passed", "failed") for row in e)
    e_attempts = all(
        row.get("model_receipts") or row.get("clarification_returned") for row in e
    )
    jev_quality = e_pass >= d_pass and e_errors <= d_errors
    jev_time_gain = 1 - time_e / time_d if time_d else None
    jev_unknown = any(row["cost"]["unknown_usage_or_cost"] for row in d + e)
    jev_cost_gain = (
        1 - cost_e / cost_d if cost_d and not jev_unknown and model != "codex" else None
    )
    return {
        "model": model,
        "primary_denominator_per_arm": 18,
        "C_passed": c_pass,
        "D_passed": d_pass,
        "E_passed": e_pass,
        "C_critical_errors": c_errors,
        "D_critical_errors": d_errors,
        "E_critical_errors": e_errors,
        "D_minus_C": d_pass - c_pass,
        "D_quality_at_least_C": quality,
        "D_time_reduction": time_gain,
        "D_cash_quote_reduction": cost_gain,
        "full_C_D_reviews_available": complete,
        "actual_C_D_attempts_available": actual_attempts,
        "query_incremental_effect_preliminary": effect,
        "query_quality_gate_16_of_18": complete and d_pass >= 16 and d_errors == 0,
        "JEV_end_task_quality_at_least_D": jev_quality,
        "JEV_time_reduction": jev_time_gain,
        "JEV_cash_quote_reduction": jev_cost_gain,
        "full_E_reviews_available": e_complete,
        "JEV_end_task_adoption_condition": complete
        and e_complete
        and actual_attempts
        and e_attempts
        and jev_quality
        and (
            (jev_time_gain is not None and jev_time_gain > 0)
            or (jev_cost_gain is not None and jev_cost_gain > 0)
        ),
        "JEV_routing_gate_separately_required": True,
        "limits": "Task completion/time under fixed budgets. Native workloads are correlated and review is performed by the implementing Codex agent, not an external blinded panel. Token quotes are not audited provider invoices.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--command-review", type=Path, required=True)
    parser.add_argument("--diagnosis-reviews", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Rollups are immutable; choose a new output directory")
    records = json.loads((args.scores / "records.json").read_text())
    sources = {
        row["episode_id"]: row
        for row in json.loads((args.sources / "records.json").read_text())
    }
    command_review = json.loads(args.command_review.read_text())
    pending_commands = defaultdict(list)
    for row in command_review["records"]:
        if row["status"] == "review_required":
            pending_commands[Path(row["events_path"]).resolve()].append(row)
    reviews = {}
    if args.diagnosis_reviews:
        supplied = json.loads(args.diagnosis_reviews.read_text())["reviews"]
        reviews = {row["episode_id"]: row for row in supplied}
        if len(reviews) != len(supplied):
            raise ValueError("Duplicate diagnosis review identities")
        expected = {row["episode_id"] for row in records if row["kind"] == "diagnosis"}
        for identity, review in reviews.items():
            if identity not in expected:
                raise ValueError(
                    "Review outside the planned diagnosis matrix: " + identity
                )
            if review["grade"] not in ("passed", "failed", "evidence_insufficient"):
                raise ValueError("Unsupported diagnosis grade: " + identity)
            if not isinstance(review.get("critical_error"), bool):
                raise ValueError(
                    "Explicit critical-error judgment required: " + identity
                )
            if review["grade"] == "passed" and review["critical_error"]:
                raise ValueError(
                    "A diagnosis with a critical error cannot pass: " + identity
                )
            checks = review.get("checks", [])
            if len({check["name"] for check in checks}) != len(checks):
                raise ValueError("Duplicate diagnosis check names: " + identity)
            if any(
                not isinstance(check.get("passed"), bool) or not check.get("reason")
                for check in checks
            ):
                raise ValueError(
                    "Each check requires a boolean and a reason: " + identity
                )
    for record in records:
        source = sources.get(record["episode_id"])
        source_flags = (
            []
            if source is None
            else [
                name
                for name in (
                    "citation_ids_passed",
                    "saved_evidence_passed",
                    "registered_originals_passed",
                    "direct_sources_passed",
                )
                if source.get(name) is False
            ]
        )
        record["source_failure_fields"] = source_flags
        folder = Path(record["folder"]).resolve() if record.get("folder") else None
        pending = [
            str(path) for path in pending_commands if folder and folder in path.parents
        ]
        record["pending_command_reviews"] = pending
        if record["kind"] == "diagnosis":
            review = reviews.get(record["episode_id"])
            if review:
                validate_review_binding(record, review)
                checks = {check["name"]: check for check in review.get("checks", [])}
                documented = REQUIRED_CHECKS <= set(checks)
                passed = documented and all(
                    checks[key]["passed"] is True for key in REQUIRED_CHECKS
                )
                if review["grade"] == "passed" and not passed:
                    raise ValueError(
                        "Cannot pass an incompletely documented diagnosis review: "
                        + record["episode_id"]
                    )
                record.update(
                    grade=review["grade"],
                    diagnosis_review=review,
                    critical_error=review["critical_error"],
                    reasonable_refusal=review.get("reasonable_refusal", False),
                    purposeful_progress=review.get("purposeful_progress", False),
                    formal_passed=review["grade"] == "passed",
                )
            elif record["measurement_status"] != "not_run":
                record["grade"] = "review_required"
        if record["grade"] == "passed" and (source is None or source_flags or pending):
            record.update(grade="evidence_insufficient", formal_passed=False)
        record["cost"] = episode_cost(record)
    if len(records) != 528 or len({row["episode_id"] for row in records}) != 528:
        raise ValueError("The complete original 528-row matrix is required")
    grouped = defaultdict(list)
    for row in records:
        grouped[
            (row["kind"], row["model"], row["arm"], row["repeat"], row["ablation"])
        ].append(row)
    groups = []
    for (kind, model, arm, repeat, ablation), rows in sorted(
        grouped.items(), key=lambda pair: str(pair[0])
    ):
        groups.append(
            {
                "kind": kind,
                "model": model,
                "arm": arm,
                "repeat": repeat,
                "ablation": ablation,
                "denominator": len(rows),
                "grades": dict(Counter(row["grade"] for row in rows)),
                "measurement_status": dict(
                    Counter(row["measurement_status"] for row in rows)
                ),
                "passed": sum(row["grade"] == "passed" for row in rows),
                "wall_seconds_total": sum(
                    row.get("wall_seconds_used") or 0 for row in rows
                ),
                "confirmed_token_quote_usd": sum(
                    row["cost"]["confirmed_token_quote_usd"] for row in rows
                ),
                "episodes_with_unknown_usage_or_cost": sum(
                    row["cost"]["unknown_usage_or_cost"] for row in rows
                ),
                "recorded_token_totals": dict(
                    sum(
                        (Counter(row["cost"]["recorded_tokens"]) for row in rows),
                        Counter(),
                    )
                ),
                "reasonable_refusals": sum(
                    row.get("reasonable_refusal") is True for row in rows
                ),
                "purposeful_progress": sum(
                    row.get("purposeful_progress") is True for row in rows
                ),
                "critical_errors": sum(
                    row.get("critical_error") is True for row in rows
                ),
            }
        )
    result = {
        "rolled_up_at": datetime.now(timezone.utc).isoformat(),
        "denominator": 528,
        "program_sha256": digest(Path(__file__)),
        "inputs": {
            str(path): digest(path)
            for path in (
                args.scores / "records.json",
                args.sources / "records.json",
                args.command_review,
            )
            + ((args.diagnosis_reviews,) if args.diagnosis_reviews else ())
        },
        "groups": groups,
        "effects": [
            effect_for(model, groups, records) for model in ("codex", "deepseek-flash")
        ],
        "preselected_A_B_C_fact_comparison": selected_direct_comparison(records),
        "engineering_gate_separate": True,
        "whole_task_effect_not_inferred_from_classification": True,
    }
    args.output.mkdir(parents=True)
    (args.output / "records.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n"
    )
    (args.output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "denominator": 528,
                "reviewed_diagnosis_episodes": len(reviews),
                "grades": dict(Counter(row["grade"] for row in records)),
            }
        )
    )


if __name__ == "__main__":
    main()

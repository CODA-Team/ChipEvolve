#!/usr/bin/env python3
"""Query the repo-local LEGO-lite skill index.

The helper is intentionally deterministic and dependency-free.  It gives
Teacher/Student agents a fast first-stage lookup over concise skill records; the
returned full-card paths can then be opened only when relevant.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX = AGENT_ROOT / "knowledge" / "index" / "skill_cards.jsonl"

TOKEN_RE = re.compile(r"[A-Za-z0-9_+%.-]+")


def tokenize(text: str) -> list[str]:
    return [tok.lower() for tok in TOKEN_RE.findall(text)]


def load_cards(path: Path) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    if not path.exists():
        raise SystemExit(f"[ERROR] missing skill index: {path}")
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            card = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"[ERROR] invalid JSON at {path}:{lineno}: {exc}") from exc
        if not isinstance(card, dict) or not card.get("skill_id"):
            raise SystemExit(f"[ERROR] invalid skill card at {path}:{lineno}")
        cards.append(card)
    return cards


def text_blob(card: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "skill_id",
        "stage",
        "group",
        "summary",
        "use_when",
        "avoid_when",
        "full_card",
    ):
        parts.append(str(card.get(key, "")))
    for key in (
        "source_handles",
        "patches",
        "metrics_to_check",
        "log_signals",
        "done_criteria",
        "keywords",
    ):
        value = card.get(key, [])
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value))
    return "\n".join(parts)


def score_card(card: dict[str, Any], query_tokens: list[str], stages: set[str]) -> float:
    blob = text_blob(card).lower()
    blob_tokens = set(tokenize(blob))
    score = 0.0
    if stages:
        if str(card.get("stage", "")).lower() in stages:
            score += 8.0
        else:
            score -= 2.0
    for tok in query_tokens:
        if tok in blob_tokens:
            score += 2.0
        elif tok and tok in blob:
            score += 0.75
    # Keep exact skill/stage keyword hits stable and easy to understand.
    query = " ".join(query_tokens)
    skill_id = str(card.get("skill_id", "")).lower()
    if query and query in blob:
        score += 3.0
    if any(tok in skill_id for tok in query_tokens):
        score += 1.5
    return score


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def format_markdown(rows: list[tuple[float, dict[str, Any]]], *, show_full: bool) -> str:
    lines = ["# Knowledge Skill Query", ""]
    if not rows:
        lines.append("No matching skill records.")
        return "\n".join(lines) + "\n"
    for score, card in rows:
        full_card = AGENT_ROOT / str(card.get("full_card", ""))
        lines.extend(
            [
                f"## {card['skill_id']} (score={score:.2f})",
                f"- stage: `{card.get('stage', '')}`",
                f"- group: `{card.get('group', '')}`",
                f"- summary: {card.get('summary', '')}",
                f"- use_when: {card.get('use_when', '')}",
                f"- avoid_when: {card.get('avoid_when', '')}",
                f"- skill_note: `{full_card}`",
                "- source_handles: " + ", ".join(f"`{x}`" for x in as_list(card.get("source_handles"))) if card.get("source_handles") else "- source_handles: none",
                "- patches: " + ", ".join(f"`{x}`" for x in as_list(card.get("patches"))) if card.get("patches") else "- patches: none",
                "- metrics_to_check: " + ", ".join(f"`{x}`" for x in as_list(card.get("metrics_to_check"))),
                "- log_signals: " + ", ".join(f"`{x}`" for x in as_list(card.get("log_signals"))),
                "- done_criteria: " + "; ".join(as_list(card.get("done_criteria"))),
                f"- rg: `rg -n \"{card['skill_id']}|{'|'.join(as_list(card.get('keywords'))[:3])}\" knowledge/index knowledge/skills knowledge/algorithms`",
                "",
            ]
        )
        if show_full and full_card.exists():
            lines.extend(["```markdown", full_card.read_text(encoding="utf-8").strip(), "```", ""])
    return "\n".join(lines) + "\n"


def validate_cards(cards: list[dict[str, Any]]) -> int:
    """Validate local index references without requiring external tools."""
    errors: list[str] = []
    seen: set[str] = set()
    for card in cards:
        skill_id = str(card.get("skill_id", ""))
        if skill_id in seen:
            errors.append(f"duplicate skill_id: {skill_id}")
        seen.add(skill_id)
        full_card = AGENT_ROOT / str(card.get("full_card", ""))
        if not full_card.exists():
            errors.append(f"{skill_id}: missing skill note {full_card}")
        for handle in as_list(card.get("source_handles")):
            if not handle.startswith(("knowledge/", "scripts/", "baseline/", "configs/")):
                continue
            handle_path = AGENT_ROOT / handle.rstrip("/")
            if not handle_path.exists():
                errors.append(f"{skill_id}: missing source handle {handle_path}")
        for patch in as_list(card.get("patches")):
            patch_path = AGENT_ROOT / patch
            if not patch_path.exists():
                errors.append(f"{skill_id}: missing patch {patch_path}")
    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1
    print(f"[OK] validated {len(cards)} skill records")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Query DPL-Evolve LEGO-lite skill records.")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--stage", action="append", default=[], help="Filter/boost one workflow stage. Repeatable.")
    parser.add_argument("--q", default="", help="Lexical query over summaries, handles, metrics, and keywords.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--show-full", action="store_true", help="Append matched markdown skill notes.")
    parser.add_argument("--json", action="store_true", help="Emit scored cards as JSON.")
    parser.add_argument("--validate", action="store_true", help="Validate index full-card and patch references.")
    args = parser.parse_args()

    cards = load_cards(args.index)
    if args.validate:
        return validate_cards(cards)

    query_tokens = tokenize(args.q)
    stages = {stage.lower() for stage in args.stage if stage}
    rows = [(score_card(card, query_tokens, stages), card) for card in cards]
    if stages:
        # Still allow out-of-stage hits when query strongly matches, but hide weak ones.
        rows = [row for row in rows if row[0] > 0]
    elif query_tokens:
        rows = [row for row in rows if row[0] > 0]
    rows.sort(key=lambda row: (row[0], str(row[1].get("skill_id", ""))), reverse=True)
    rows = rows[: max(1, args.limit)]

    if args.json:
        payload = [dict(card, score=round(score, 3)) for score, card in rows]
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(format_markdown(rows, show_full=args.show_full), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Review conservative command flags without modifying the frozen auditor.

Only literal local decision-file writes, schema reads and execution of the exact
assigned bridge are mechanically cleared. Everything else requires human review.
No model-produced command or Python expression is executed by this program.
"""

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex


PROTECTED = {
    "state.json",
    "config.json",
    "decision-schema.json",
    "host-schema.json",
    "action-schema.json",
}
SCHEMAS = {"decision-schema.json", "host-schema.json", "action-schema.json"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_json(name, folder, *, schema=False):
    path = Path(name)
    path = path if path.is_absolute() else folder / path
    return (
        path.resolve().parent == folder.resolve()
        and path.suffix == ".json"
        and (path.name in SCHEMAS if schema else path.name not in PROTECTED)
    )


def unwrap(command):
    parts = shlex.split(command)
    shell = bool(parts) and Path(parts[0]).name in ("bash", "sh", "zsh", "dash")
    return (
        parts[-1]
        if shell and len(parts) >= 3 and parts[-2] in ("-lc", "-c")
        else command
    )


def python_literal(code, folder):
    """A small static grammar; unknown constructs are left for explicit review."""
    tree = ast.parse(code)
    names = set()
    imports = set()
    reads, writes = [], []

    def expression(node):
        if isinstance(node, ast.Constant):
            return isinstance(node.value, (str, int, float, bool, type(None)))
        if isinstance(node, ast.Name):
            return node.id in names
        if isinstance(node, (ast.List, ast.Tuple)):
            return all(expression(item) for item in node.elts)
        if isinstance(node, ast.Dict):
            return all(
                key is not None and expression(key) and expression(value)
                for key, value in zip(node.keys, node.values)
            )
        if isinstance(node, ast.UnaryOp):
            return isinstance(node.op, (ast.UAdd, ast.USub)) and expression(
                node.operand
            )
        if isinstance(node, ast.BinOp):
            return (
                isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div))
                and expression(node.left)
                and expression(node.right)
            )
        if not isinstance(node, ast.Call):
            return False
        fn = node.func
        if node.keywords and not (
            isinstance(fn, ast.Attribute)
            and isinstance(fn.value, ast.Name)
            and fn.value.id == "json"
            and fn.attr in ("dump", "dumps")
            and all(
                key.arg in ("indent", "ensure_ascii", "sort_keys", "separators")
                and expression(key.value)
                for key in node.keywords
            )
        ):
            return False
        if isinstance(fn, ast.Name) and fn.id == "print":
            return all(expression(value) for value in node.args)
        if (
            isinstance(fn, ast.Attribute)
            and isinstance(fn.value, ast.Name)
            and fn.value.id == "json"
            and fn.attr == "dumps"
            and "json" in imports
        ):
            return len(node.args) == 1 and expression(node.args[0])
        if (
            isinstance(fn, ast.Attribute)
            and isinstance(fn.value, ast.Name)
            and fn.value.id == "json"
            and fn.attr == "dump"
            and "json" in imports
            and len(node.args) == 2
            and expression(node.args[0])
        ):
            target = node.args[1]
            if (
                isinstance(target, ast.Call)
                and isinstance(target.func, ast.Name)
                and target.func.id == "open"
                and not target.keywords
                and len(target.args) == 2
                and all(
                    isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                    for arg in target.args
                )
                and target.args[1].value == "w"
                and local_json(target.args[0].value, folder)
            ):
                writes.append(target.args[0].value)
                return True
            return False
        if not (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Call)):
            return False
        target = fn.value
        if not (
            isinstance(target.func, ast.Name)
            and target.func.id == "Path"
            and "Path" in imports
            and len(target.args) == 1
            and not target.keywords
            and isinstance(target.args[0], ast.Constant)
            and isinstance(target.args[0].value, str)
        ):
            return False
        name = target.args[0].value
        if (
            fn.attr == "read_text"
            and not node.args
            and local_json(name, folder, schema=True)
        ):
            reads.append(name)
            return True
        if (
            fn.attr == "write_text"
            and len(node.args) == 1
            and local_json(name, folder)
            and expression(node.args[0])
        ):
            writes.append(name)
            return True
        return False

    for node in tree.body:
        if isinstance(node, ast.Import):
            if any(alias.name != "json" or alias.asname for alias in node.names):
                return None
            imports.add("json")
        elif isinstance(node, ast.ImportFrom):
            if not (
                node.module == "pathlib"
                and node.level == 0
                and len(node.names) == 1
                and node.names[0].name == "Path"
                and not node.names[0].asname
            ):
                return None
            imports.add("Path")
        elif isinstance(node, ast.Assign):
            if (
                len(node.targets) != 1
                or not isinstance(node.targets[0], ast.Name)
                or node.targets[0].id in ("Path", "json", "print")
                or not expression(node.value)
            ):
                return None
            names.add(node.targets[0].id)
        elif isinstance(node, ast.Expr):
            if not expression(node.value):
                return None
        else:
            return None
    return {
        "kind": "static_literal_python",
        "schema_reads": reads,
        "decision_writes": writes,
    }


def inspect(command, event_path):
    folder = event_path.parent
    lines = unwrap(command).splitlines()
    checks = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        index += 1
        if not line:
            continue
        python_input = re.fullmatch(
            r"(?:\S*/)?python(?:3(?:\.\d+)?)?\s+-\s*<<\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\1",
            line,
        )
        if python_input:
            body = []
            while index < len(lines) and lines[index].strip() != python_input.group(2):
                body.append(lines[index])
                index += 1
            if index == len(lines):
                return None
            index += 1
            result = python_literal("\n".join(body), folder)
            if result is None:
                return None
            checks.append(result)
            continue
        match = re.fullmatch(
            r"cat\s+>\s*(\S+)\s*<<\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\2", line
        )
        if match:
            name = match.group(1)
            if not local_json(name, folder):
                return None
            body = []
            while index < len(lines) and lines[index].strip() != match.group(3):
                body.append(lines[index])
                index += 1
            if index == len(lines):
                return None
            index += 1
            value = json.loads("\n".join(body))
            if not isinstance(value, dict):
                return None
            checks.append(
                {"kind": "quoted_literal_json_heredoc", "decision_write": name}
            )
            continue
        parts = shlex.split(line)
        while parts and parts[0] in (
            "HTTP_PROXY=",
            "HTTPS_PROXY=",
            "ALL_PROXY=",
            "http_proxy=",
            "https_proxy=",
            "all_proxy=",
        ):
            parts.pop(0)
        if not parts or not re.fullmatch(
            r"python(?:3(?:\.\d+)?)?", Path(parts[0]).name
        ):
            return None
        if len(parts) == 3 and parts[1] == "-c":
            result = python_literal(parts[2], folder)
            if result is None:
                return None
            checks.append(result)
            continue
        bridge_args = parts[2:]
        if bridge_args and bridge_args[0] == "act":
            bridge_args = bridge_args[1:]
        if (
            len(bridge_args) != 2
            or bridge_args[0] != "--decision"
            or not local_json(bridge_args[1], folder)
        ):
            return None
        bridge = Path(parts[1])
        bridge = bridge if bridge.is_absolute() else folder / bridge
        assigned = folder / "action.py"
        if bridge.resolve() != assigned.resolve() or not assigned.is_file():
            return None
        checks.append(
            {
                "kind": "exact_assigned_bridge",
                "path": str(assigned),
                "sha256": digest(assigned),
                "decision_read": bridge_args[1],
            }
        )
    return checks or None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manual-review", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Review records are immutable; use a new output path")
    audit = json.loads(args.audit.read_text())
    manual = {}
    if args.manual_review:
        for decision in json.loads(args.manual_review.read_text())["records"]:
            key = (
                str(Path(decision["events_path"]).resolve()),
                decision["action_index"],
            )
            if (
                key in manual
                or decision["decision"] != "cleared_manual_local_setup"
                or not decision["rationale"]
            ):
                raise ValueError("Invalid or duplicate manual command adjudication")
            manual[key] = decision
    records = []
    for episode in audit["episodes"]:
        if not episode["requires_review"]:
            continue
        path = Path(episode["path"])
        unchanged = path.is_file() and digest(path) == episode["sha256"]
        for index, action in enumerate(episode["actions"]):
            if action["status"] != "requires_review":
                continue
            try:
                checks = inspect(action["command"], path) if unchanged else None
            except (ValueError, SyntaxError, OSError):
                checks = None
            row = {
                "events_path": str(path),
                "events_sha256": episode["sha256"],
                "action_index": index,
                "command_sha256": hashlib.sha256(
                    action["command"].encode()
                ).hexdigest(),
                "original_flag": action,
                "status": "cleared_literal_local_setup"
                if checks
                else "review_required",
                "checks": checks,
                "source_unchanged": unchanged,
                "rationale": "Only quoted JSON/local static values, declared schemas and exact assigned bridge."
                if checks
                else "Source changed or command lies outside the narrow static review grammar.",
            }
            decision = manual.get((str(path.resolve()), index))
            if decision:
                if (
                    not unchanged
                    or decision["events_sha256"] != episode["sha256"]
                    or decision["command_sha256"] != row["command_sha256"]
                ):
                    raise ValueError(
                        "Manual review does not match current exact event/command: "
                        + str(path)
                    )
                row.update(
                    status=decision["decision"],
                    manual_review=decision,
                    rationale=decision["rationale"],
                )
            records.append(row)
        for kind in ("file_changes", "external_tools"):
            for index, action in enumerate(episode.get(kind, [])):
                if action["status"] == "requires_review":
                    records.append(
                        {
                            "events_path": str(path),
                            "events_sha256": episode["sha256"],
                            "kind": kind,
                            "index": index,
                            "original_flag": action,
                            "status": "review_required",
                            "source_unchanged": unchanged,
                        }
                    )
    result = {
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "audit_path": str(args.audit),
        "audit_sha256": digest(args.audit),
        "review_program_sha256": digest(Path(__file__)),
        "grades": dict(Counter(row["status"] for row in records)),
        "records": records,
        "limit": "Supplemental review only; original frozen flags are retained. Does not grade model answers.",
    }
    if args.manual_review:
        result["manual_review_path"] = str(args.manual_review)
        result["manual_review_sha256"] = digest(args.manual_review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"grades": result["grades"], "record_count": len(records)}))


if __name__ == "__main__":
    main()

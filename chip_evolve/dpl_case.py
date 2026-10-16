"""Bind the native problem header to the registered physical design."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import write
from .jobs import digest


def prepare_case(controller: Path, design: dict[str, Any]) -> str:
    template = controller / "problems" / design["dpl_case"] / "problem.yaml"
    text, template_hash = template.read_text(), digest(template)
    case_id = design["nickname"] + "_" + design["platform"]
    fields = {
        "name": case_id + "_legalizer_wl",
        "design": design["nickname"],
        "platform": design["platform"],
        "design_config": "./" + design["orfs_config"],
    }
    for key, value in fields.items():
        text, count = re.subn(
            r"(?m)^" + key + r":.*$",
            lambda _, replacement=key + ": " + value: replacement,
            text,
            count=1,
        )
        if count != 1:
            raise ValueError("Native DPL problem template lacks " + key)
    target = controller / "problems" / case_id / "problem.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    write(
        controller.parent / "dpl-case-binding.json",
        {
            "case_id": case_id,
            "template_case": design["dpl_case"],
            "template_sha256": template_hash,
            "problem_sha256": digest(target),
            **fields,
        },
    )
    return case_id

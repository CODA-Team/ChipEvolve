"""Load auditable investigation skills from installed package resources."""

from __future__ import annotations

import hashlib
import re
from importlib.resources import files

from query_agent.domain.investigation import SkillRecord


class InstalledInvestigationSkills:
    def load(self, names: list[str]) -> list[SkillRecord]:
        known = {
            "timing-degradation",
            "experiment-comparison",
            "tool-failure",
            "task-handoff",
        }
        if set(names) - known:
            raise ValueError("unknown investigation skill")
        records: list[SkillRecord] = []
        for name in names:
            content = files("query_agent.skills").joinpath(name, "SKILL.md").read_text()
            version = re.search(
                r"^version: ([0-9]+\.[0-9]+\.[0-9]+)$", content, re.MULTILINE
            )
            if version is None:
                raise ValueError("skill must declare a semantic version")
            records.append(
                SkillRecord(
                    name=name,
                    version=version[1],
                    sha256=hashlib.sha256(content.encode()).hexdigest(),
                    content=content,
                )
            )
        return records

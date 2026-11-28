"""Pure acceptance rules for recorded Yosys and EQY proofs."""

from __future__ import annotations

import re
from typing import Any


def qualified_strategy(policy: dict[str, Any]) -> str:
    strategy = policy.get("equivalence_strategy", "sat")
    if strategy == "sat":
        raise ValueError(
            "Legacy EQY SAT failed the fixed-Liberty sequential negative control; "
            "configure equivalence_strategy=abc-pdr and its pinned solver manifest"
        )
    if strategy != "abc-pdr":
        raise ValueError("Unknown EQY strategy: " + str(strategy))
    return strategy


def proven_points(log: str) -> int:
    counts = re.findall(r"Of those cells (\d+) are proven and (\d+) are unproven", log)
    if (
        not counts
        or int(counts[-1][0]) == 0
        or int(counts[-1][1]) != 0
        or "Equivalence successfully proven!" not in log
    ):
        raise ValueError("No complete nonempty equivalence proof in the Yosys receipt")
    return int(counts[-1][0])

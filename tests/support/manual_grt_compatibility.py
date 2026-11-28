"""Adapt the existing manual GRT resize/buffer recipe to the pinned tool.

This is an internal script migration, not a replacement optimization algorithm.
The caller must retain the original script and submit a new copy through EF.
"""

from __future__ import annotations

import re

_INSERT = "insert_buffer -buffer_cell BUF_X4 -net [$net getName]"


def adapt_manual_grt_script(script: str) -> str:
    """Preserve selected drivers/cells; initialize grid, refresh RC, name buffers.

    sta::replace_cell invalidates the estimator's incremental state. Placement
    estimation clears that state, then GRT estimation restores the intended RC.
    Explicit names avoid the pinned insert_buffer wrapper's null-name path.
    The native insertion also calls legalCellPos without initializing its grid;
    check_placement initializes that grid without optimizing the source layout.
    """
    if "global_route -start_incremental\n" not in script:
        raise ValueError("Expected an existing incremental GRT recipe")
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return (
            "estimate_parasitics -placement\n"
            "estimate_parasitics -global_routing\n"
            + match.group(0)
            + f" -buffer_name ce_manual_buffer_{count}"
            + f" -net_name ce_manual_net_{count}"
        )

    adapted = script.replace(
        "global_route -start_incremental\n",
        "check_placement\nglobal_route -start_incremental\n",
        1,
    )
    adapted = re.sub(r"(?m)^" + re.escape(_INSERT) + r"$", replace, adapted)
    if not count:
        raise ValueError("Expected the original explicit BUF_X4 insertion recipe")
    return adapted

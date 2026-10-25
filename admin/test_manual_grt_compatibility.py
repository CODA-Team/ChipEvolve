"""Compatibility must retain native strategy, routing model and action order."""

import pytest

from admin.manual_grt_compatibility import adapt_manual_grt_script


def test_repeated_driver_actions_keep_cells_and_restore_grt_before_each_buffer():
    header = "read_db {source.odb}\nglobal_route -start_incremental\n"
    action = (
        "sta::replace_cell {driver} [get_lib_cells */NOR3_X4]\n"
        "insert_buffer -buffer_cell BUF_X4 -net [$net getName]\n"
    )
    tail = "repair_design\nglobal_route -end_incremental\n"
    original = header + action + action.replace("{driver}", "{other}") + tail
    adapted = adapt_manual_grt_script(original)
    assert adapted.startswith(
        "read_db {source.odb}\ncheck_placement\nglobal_route -start_incremental\n"
    )
    assert adapted.endswith(tail)
    assert "detailed_placement" not in adapted
    assert adapted.count("sta::replace_cell") == 2
    for index, driver in enumerate(("driver", "other"), 1):
        assert (
            f"sta::replace_cell {{{driver}}} [get_lib_cells */NOR3_X4]\n"
            "estimate_parasitics -placement\n"
            "estimate_parasitics -global_routing\n"
            "insert_buffer -buffer_cell BUF_X4 -net [$net getName]"
            f" -buffer_name ce_manual_buffer_{index}"
            f" -net_name ce_manual_net_{index}\n"
        ) in adapted
    assert "-buffer_name" not in original


@pytest.mark.parametrize(
    "script",
    [
        "insert_buffer -buffer_cell BUF_X4 -net [$net getName]\n",
        "global_route -start_incremental\nrepair_design\n",
        "global_route -start_incremental\ninsert_buffer -buffer_cell BUF_X2\n",
    ],
)
def test_other_recipes_are_not_silently_rewritten(script):
    with pytest.raises(ValueError):
        adapt_manual_grt_script(script)

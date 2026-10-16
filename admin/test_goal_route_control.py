"""A routing control must preserve checkpoints and placement/routing commands."""

import pytest

from admin.goal_route_control import without_repairs


def test_control_removes_actions_but_preserves_reports_and_physical_pipeline():
    text = 'read_def {input.def}\nrepair_design\nrepair_power -phase early_forced_reclaim -proportion 80\nputs "post_repair_power"\ndetailed_placement\nglobal_route\nwrite_db {post_route.odb}\n'
    control, removed = without_repairs(text)
    assert removed == [
        "repair_design",
        "repair_power -phase early_forced_reclaim -proportion 80",
    ]
    assert (
        control
        == 'read_def {input.def}\nputs "post_repair_power"\ndetailed_placement\nglobal_route\nwrite_db {post_route.odb}\n'
    )
    assert "repair_power -phase" in text


@pytest.mark.parametrize(
    "text",
    [
        "repair_design\n",
        "repair_power -phase p \\\n  -proportion 80\n",
        "repair_power -phase {complex}\n",
    ],
)
def test_unsupported_controls_are_rejected_instead_of_partially_removing_actions(text):
    with pytest.raises(ValueError):
        without_repairs(text)

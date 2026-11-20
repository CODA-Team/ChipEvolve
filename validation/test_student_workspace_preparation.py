"""The platform prepares the branch picked by the Teacher before prompting."""

import subprocess
from types import SimpleNamespace

import pytest

from scripts.teacher_loop.common import student_workspace_paths
from scripts.teacher_loop.execution import inline_teacher_plan_for_children
from scripts.teacher_loop.workspace_scripts import write_student_workspace_scripts


@pytest.mark.parametrize(
    ("platform", "assignment", "expected"),
    [
        (True, "start/donor family: diamond", "01 --kind diamond"),
        (True, "continuation parent: keep elite", "00"),
        (False, "start/donor family: diamond", None),
    ],
)
def test_teacher_assignment_reaches_workspace(tmp_path, platform, assignment, expected):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Student task")
    teacher = tmp_path / "teacher.md"
    teacher.write_text(
        f"### student_01\n- {assignment}\n\n### student_02\nOther work\n"
    )
    scripts = tmp_path / "scripts/student_01"
    scripts.mkdir(parents=True)
    for script, phase in [
        ("00_prepare_source.sh", "00"),
        ("01_prepare_start_source.sh", "01"),
    ]:
        path = scripts / script
        path.write_text(f'#!/bin/sh\necho "{phase} $*"\n')
        path.chmod(0o755)
    child = SimpleNamespace(
        prompt_path=prompt,
        student_id="student_01",
        student_workspace=tmp_path,
        source_base_record=tmp_path / "artifacts/source_base_commit.txt",
    )

    inline_teacher_plan_for_children(
        child_rounds=[child], teacher_last_message=teacher, prepare_workspaces=platform
    )

    log = child.source_base_record.with_name("workspace-prepare.log")
    if expected:
        assert log.read_text().strip() == expected
        assert "The controller prepared your source" in prompt.read_text()
    else:
        assert not log.exists()
        assert "prepare_start_source_script --kind diamond" in prompt.read_text()
    assert "Other work" not in prompt.read_text()


def test_platform_rejects_another_students_start(tmp_path):
    teacher = tmp_path / "teacher.md"
    teacher.write_text("### student_01\n- start/donor family: diamond\n")
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Student task")
    child = SimpleNamespace(prompt_path=prompt, student_id="student_02")

    with pytest.raises(ValueError, match="did not assign student_02"):
        inline_teacher_plan_for_children(
            child_rounds=[child], teacher_last_message=teacher, prepare_workspaces=True
        )
    assert prompt.read_text() == "Student task"


def test_measure_active_trial_without_finalizing(tmp_path):
    paths = student_workspace_paths(
        round_dir=tmp_path, iteration=1, student_id="student_01"
    )
    runtime = SimpleNamespace(
        agent_root=tmp_path, orfs_root=tmp_path / "orfs", state_root=tmp_path
    )
    scripts = write_student_workspace_scripts(
        runtime=runtime,
        paths=paths,
        case_id="gcd_nangate45",
        flow_variant="smoke",
        threads=2,
        start_kind="framework",
        run_tag="trial",
        parent_src=tmp_path / "seed",
        use_seed_override=False,
        timeout_seconds=None,
    )
    for stage in ("build", "evaluate", "finalize"):
        scripts[stage].write_text(f"#!/bin/sh\necho {stage}\n")
    assert subprocess.check_output(
        [scripts["after_edit"], "--measure-only"], text=True
    ).splitlines() == ["build", "evaluate"]
    assert subprocess.check_output([scripts["after_edit"]], text=True).splitlines() == [
        "build",
        "evaluate",
        "finalize",
    ]

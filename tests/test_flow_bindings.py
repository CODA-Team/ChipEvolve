import json

from eda_toolkits.openroad.flow import run_flow


def test_stock_orfs_consumes_staged_config_constraints_and_actual_libraries(
    tmp_path, monkeypatch
):
    image = tmp_path / "image.sif"
    image.write_bytes(b"test")
    for name in ("design.mk", "common.sdc", "same_name_FF.lib"):
        (tmp_path / name).write_text("test input")
    monkeypatch.setattr("eda_toolkits.openroad.flow.require_eda_memory", lambda: None)
    monkeypatch.setattr(
        "eda_toolkits.openroad.flow.shutil.which", lambda _: "/apptainer"
    )
    captured = []

    def execute(command, workspace):
        captured.extend(command)
        (workspace / "flow/results").mkdir(parents=True)
        (workspace / "flow/results/6_final.odb").write_bytes(b"test output")
        return 0

    monkeypatch.setattr("eda_toolkits.openroad.flow.run_logged", execute)
    result = tmp_path / "result.json"
    assert (
        run_flow(
            result,
            "now",
            tmp_path,
            {
                "orfs_image": str(image),
                "design_config": "designs/asap7/second/config.mk",
                "revision_id": "experiment",
                "config_path": "design.mk",
                "sdc_path": "common.sdc",
                "liberty_paths": ["same_name_FF.lib"],
            },
        )
        == 0
    )
    assert "DESIGN_CONFIG=/work/design.mk" in captured
    assert "SDC_FILE=/work/common.sdc" in captured
    assert "LIB_FILES=/work/same_name_FF.lib" in captured
    assert json.loads(result.read_text())["status"] == "succeeded"

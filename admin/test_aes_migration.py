"""Migration must freeze the formal evaluator instead of a stale flow template."""

from admin.test_local_business import deployment
from chip_evolve.config import read, write
from chip_evolve.jobs import digest
from chip_evolve.professional import flow_source, tool_profile


def test_formal_cp0_evaluator_and_profile_identity_replace_the_old_template(tmp_path):
    d = deployment(tmp_path)
    template, formal, experiment = (
        tmp_path / "template",
        tmp_path / "formal",
        tmp_path / "experiment",
    )
    (template / "flow/designs/asap7/another").mkdir(parents=True)
    (template / "flow/platforms/asap7/lib/NLDM").mkdir(parents=True)
    (formal / "flow").mkdir(parents=True)
    experiment.mkdir()
    (template / "flow/designs/asap7/another/config.mk").write_text("original config\n")
    for name in ("eval_tns.sh", "eval_tns.tcl"):
        (template / "flow" / name).write_text("old evaluator")
        (formal / "flow" / name).write_text("current formal evaluator")
    (template / "flow/maindriver.sh").write_text("stale batch controller")
    (formal / "flow/maindriver.sh").write_text(
        "current controller with explicit stage closure"
    )
    (formal / "run.sh").write_text("native controller")
    (template / "flow/Makefile").write_text("original Makefile")
    library = tmp_path / "fixed.lib"
    library.write_text("fixed library")
    profile = tmp_path / "profile.json"
    write(profile, {"flow_dir": str(template / "flow"), "eval_tns_sha256": "old"})
    d.value.update(
        flow_template=str(template),
        flow_tool_profile=str(profile),
        professional={"flow": {"source": str(formal)}},
        designs={
            "another": {
                "platform": "asap7",
                "libraries": [{"path": str(library)}],
                "orfs_config": "designs/asap7/another/config.mk",
            },
            "unqualified": {
                "platform": "asap7",
                "libraries": [{"path": str(tmp_path / "unavailable.lib")}],
                "orfs_config": "designs/asap7/not-in-template/config.mk",
            },
        },
    )
    source = flow_source(d, experiment, design_id="another")
    frozen = tool_profile(d, source, experiment)
    assert (source / "flow/eval_tns.sh").read_text() == "current formal evaluator"
    assert (
        source / "flow/maindriver.sh"
    ).read_text() == "current controller with explicit stage closure"
    assert read(frozen)["eval_tns_sha256"] == digest(formal / "flow/eval_tns.tcl")
    assert read(frozen)["eval_tns_sha256"] != digest(template / "flow/eval_tns.tcl")

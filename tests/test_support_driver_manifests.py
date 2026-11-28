"""Moved evidence drivers must resolve real files and remain executable in EF."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.support import accept_common_toolchain as acceptance
from tests.support import overnight_runtime as overnight
from tests.support import qualify_common_toolchain as qualification
from tests.support import run_a2_stage_acceptance as stages

QUALIFICATION_NAMES = {
    "qualify_common_toolchain.py",
    "accept_common_toolchain.py",
    "run_dplevolve_native.py",
    "run_goalevolve_native.py",
}
STAGE_NAMES = {
    "run_a2_stage_acceptance.py",
    "prepare_a2_stage_inputs.py",
    "a2_stage_cancellation.py",
    "measure_http_cancellation.py",
    "a2_physical_import.py",
    "a2_feedback_snapshot.py",
    "query_a2_feedback.py",
    "flow_native_baseline.py",
}


@pytest.mark.parametrize(
    "module,names", [(qualification, QUALIFICATION_NAMES), (stages, STAGE_NAMES)]
)
def test_manifest_hashes_actual_source_files_with_plain_filenames(module, names):
    inventory = module.driver_inventory(module.SUPPORT_ROOT)
    assert set(inventory) == names
    for name, sha in inventory.items():
        path = module.SUPPORT_ROOT / name
        assert path.is_file()
        assert path.name == name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha


@pytest.mark.parametrize("module", [qualification, stages])
def test_incomplete_driver_source_fails_before_starting_work(tmp_path, module):
    with pytest.raises(FileNotFoundError):
        module.driver_inventory(tmp_path)


def test_ef_staging_preserves_names_and_flat_import_closure(tmp_path):
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    rows = qualification.staged_driver_inputs(qualification.SUPPORT_ROOT)
    assert {row["destination"] for row in rows} == {
        "inputs/qualify_common_toolchain.py",
        "inputs/run_dplevolve_native.py",
        "inputs/run_goalevolve_native.py",
    }
    for row in rows:
        source, destination = Path(row["source"]), attempt / row["destination"]
        assert source.is_file()
        assert destination.name == source.name
        destination.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, destination)
    # Site packages and the project root are absent: success requires the
    # exact three-file payload's sibling imports, as on the EF command path.
    process = subprocess.run(
        [
            sys.executable,
            "-E",
            "-S",
            str(attempt / "inputs/qualify_common_toolchain.py"),
            "--help",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    assert "leaf" in process.stdout


def test_staging_rejects_missing_source_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        qualification.staged_driver_inputs(tmp_path)


def test_controller_rejects_changed_driver_before_service_submission(
    tmp_path, monkeypatch
):
    from eda_toolkits import orfs

    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "driver_root": str(qualification.SUPPORT_ROOT),
                "driver_files": {"qualify_common_toolchain.py": "0" * 64},
            }
        )
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Changed frozen source must not start an EF client")

    monkeypatch.setattr("openroad_platform_client.KernelClient", forbidden)
    monkeypatch.setattr(orfs, "OrfsToolkit", forbidden)
    with pytest.raises(ValueError, match="Qualification source changed after freeze"):
        qualification.controller(tmp_path)


@pytest.mark.parametrize(
    "script", ["accept_common_toolchain.py", "overnight_runtime.py"]
)
def test_direct_driver_entry_resolves_sibling_imports(tmp_path, script):
    source = qualification.SUPPORT_ROOT
    names = QUALIFICATION_NAMES | {"overnight_runtime.py", "run_common_goalevolve.py"}
    for name in names:
        shutil.copyfile(source / name, tmp_path / name)
    process = subprocess.run(
        [sys.executable, "-E", "-S", str(tmp_path / script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr


def test_capture_environment_uses_the_real_acceptance_manifest(tmp_path, monkeypatch):
    def metadata(command, **kwargs):
        if command[0] != "git":
            return b"[]"
        if command[1] in {"ls-files", "diff"}:
            return b""
        return "a" * 40 + "\n"

    monkeypatch.setattr(stages.subprocess, "check_output", metadata)
    record = stages.capture_environment(tmp_path / "capture", os.environ.copy())
    assert set(record["acceptance"]["files"]) == STAGE_NAMES
    assert record["acceptance"]["files"] == stages.driver_inventory(stages.SUPPORT_ROOT)
    assert json.loads((tmp_path / "capture/manifest.json").read_text()) == record


def test_acceptance_honors_frozen_original_and_current_driver_roots(tmp_path):
    original, configured = tmp_path / "original", tmp_path / "configured"
    config = {
        "driver_root": str(configured),
        "driver_files": {"qualify_common_toolchain.py": "old"},
    }
    before = json.dumps(config, sort_keys=True)
    repair = {
        "data_completion": {
            "original_driver_root": str(original),
            "current_driver_sha256": {"run_goalevolve_native.py": "current"},
        }
    }
    identities = acceptance.driver_identities(config, repair)
    assert identities == {
        original / "qualify_common_toolchain.py": "old",
        qualification.SUPPORT_ROOT / "run_goalevolve_native.py": "current",
    }
    assert acceptance.driver_identities(config, {}) == {
        configured / "qualify_common_toolchain.py": "old"
    }
    assert acceptance.driver_identities(
        {"driver_files": config["driver_files"]}, {}
    ) == {qualification.SUPPORT_ROOT / "qualify_common_toolchain.py": "old"}
    assert json.dumps(config, sort_keys=True) == before


def test_overnight_gateway_admits_the_directory_containing_its_leaf(
    tmp_path, monkeypatch
):
    prior = tmp_path / "prior"
    prior.mkdir()
    (prior / "config.json").write_text(
        json.dumps(
            {"image": "image.sif", "toolchain": {}, "client_python": sys.executable}
        )
    )
    monkeypatch.setattr(overnight, "U4", prior)
    ports = iter([29710, 29934])
    monkeypatch.setattr(overnight, "available_port", lambda: next(ports))
    monkeypatch.setattr(overnight.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(overnight, "configure_adapter_ceiling", lambda *a: None)
    commands = []

    def launch(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(pid=1234)

    monkeypatch.setattr(overnight.subprocess, "Popen", launch)
    monkeypatch.setattr(overnight, "http", lambda *a: {"status": "ok"})
    state = tmp_path / "instance"
    state.mkdir()
    overnight.start(state)
    gateway = commands[0]
    admitted = [
        Path(gateway[i + 1])
        for i, value in enumerate(gateway)
        if value == "--input-root"
    ]
    leaf = Path(overnight.__file__).resolve()
    assert leaf.parent in admitted
    assert leaf.parent == qualification.SUPPORT_ROOT
    assert qualification.ROOT / "admin" not in admitted

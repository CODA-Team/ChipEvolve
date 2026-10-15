"""A prebuilt professional method remains visible in its isolated runtime."""

from chip_evolve.config import read
from chip_evolve.jobs import digest
from chip_evolve.professional import materialize_dpl_replay


def test_verified_installation_and_receipt_are_preserved_under_mounted_state(tmp_path):
    installation = tmp_path / "historical-variant/install/OpenROAD"
    (installation / "bin").mkdir(parents=True)
    original = installation / "bin/openroad"
    original.write_bytes(b"verified existing binary bytes")
    original.chmod(0o755)
    receipt = installation / "bin/platform-build.json"
    receipt.write_text(
        '{"source":"/frozen/original/source","source_files":{"a":"sha"}}\n'
    )
    experiment = tmp_path / "current-experiment"
    experiment.mkdir()
    state = experiment / "native-state"
    state.mkdir()
    binary = materialize_dpl_replay(installation, state, experiment)
    assert binary.is_relative_to(state)
    assert binary.read_bytes() == original.read_bytes()
    assert binary.stat().st_mode & 0o111
    assert (binary.parent / receipt.name).read_bytes() == receipt.read_bytes()
    identity = read(experiment / "prebuilt-replay-identity.json")
    assert identity["binary_sha256"] == digest(original)
    assert identity["build_receipt_sha256"] == digest(receipt)

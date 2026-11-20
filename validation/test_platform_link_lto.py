"""The common compiler honors the already requested single LTO worker."""

import shlex
from types import SimpleNamespace

import pytest

from scripts.workspace import build_openroad_variant_relink as build


def test_explicit_core_does_not_need_a_git_checkout_in_the_relink_container(
    tmp_path, monkeypatch
):
    core = tmp_path / "core"
    monkeypatch.setattr(build.sys, "argv", ["relink", "--core-root", str(core)])
    monkeypatch.setattr(build, "maybe_delegate", lambda *_args: None)
    monkeypatch.setattr(
        build,
        "resolve_runtime_paths",
        lambda **_kwargs: SimpleNamespace(
            orfs_root=tmp_path / "orfs", agent_root=tmp_path, state_root=tmp_path
        ),
    )
    monkeypatch.setattr(
        build.subprocess, "check_output", lambda *args, **kwargs: pytest.fail("ran Git")
    )
    with pytest.raises(SystemExit, match="Missing common-core compile_commands"):
        build.main()


@pytest.mark.parametrize("platform", [False, True])
@pytest.mark.parametrize("explicit_single_worker", [False, True])
def test_real_relink_keeps_flags_paths_and_native_mode(
    tmp_path, monkeypatch, platform, explicit_single_worker
):
    monkeypatch.delenv("DPL_EVOLVE_PLATFORM_PROFILE", raising=False)
    if platform:
        monkeypatch.setenv("DPL_EVOLVE_PLATFORM_PROFILE", "selected-platform.json")
    core = tmp_path / "core"
    link = core / "src/CMakeFiles/openroad.dir/link.txt"
    link.parent.mkdir(parents=True)
    flags = ["-O3", "-flto=auto", "-fno-fat-lto-objects"]
    if explicit_single_worker:
        flags.append("-flto=1")
    arguments = [
        "/usr/bin/c++",
        *flags,
        "object with spaces.o",
        "dpl_evolve/dpl_evolve.a",
        "-o",
        "../bin/openroad",
    ]
    link.write_text(shlex.join(arguments) + "\n")
    seen = []
    monkeypatch.setattr(
        build, "run_shell", lambda command, **kw: seen.append((command, kw))
    )
    variant, installation = tmp_path / "variant", tmp_path / "install"
    result = build.relink_openroad(
        core_build=core, variant_build=variant, install_root=installation
    )
    expected = list(arguments)
    if platform and explicit_single_worker:
        expected.remove("-flto=auto")
    expected[expected.index("dpl_evolve/dpl_evolve.a")] = str(
        variant / "src/dpl_evolve/dpl_evolve.a"
    )
    expected[-1] = str(installation / "bin/openroad")
    assert result == installation / "bin/openroad"
    assert len(seen) == 1 and shlex.split(seen[0][0]) == expected
    assert seen[0][1]["cwd"] == core / "src"

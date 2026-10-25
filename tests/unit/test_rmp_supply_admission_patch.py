"""Compile the exact native predicate to check supply and signal boundaries."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class RmpSupplyAdmissionPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        project = Path(__file__).resolve().parents[2]
        fixture = project / "tests/fixtures/rmp_original_sequential_predicate.cc"
        harness = (project / "tests/fixtures/rmp_signal_guard_harness.cc").read_text()
        compiler = shutil.which("c++")
        if compiler is None:
            raise RuntimeError(
                "C++ compiler is required for native predicate regression"
            )
        target = cls.root / "src/rmp/src/Restructure.cpp"
        target.parent.mkdir(parents=True)
        target.write_text(fixture.read_text())
        patch = project / "toolchain/patches/fix-rmp-supply-sequential-admission.patch"
        subprocess.run(
            ["git", "apply", "--check", str(patch)], cwd=cls.root, check=True
        )
        subprocess.run(["git", "apply", str(patch)], cwd=cls.root, check=True)
        cls.original = cls.root / "original"
        cls.patched = cls.root / "patched"
        for binary, predicate in (
            (cls.original, fixture.read_text()),
            (cls.patched, target.read_text()),
        ):
            source = binary.with_suffix(".cc")
            source.write_text(
                harness.replace("// INSERT_EXACT_NATIVE_PREDICATE", predicate)
            )
            subprocess.run(
                [
                    compiler,
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    str(source),
                    "-o",
                    str(binary),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

    def run_case(self, binary: Path, case: int) -> bool:
        result = subprocess.run(
            [str(binary), str(case)], text=True, capture_output=True, check=True
        )
        self.assertIn(result.stdout, ("0\n", "1\n"))
        return result.stdout == "1\n"

    def test_original_predicate_reproduces_both_shared_supply_false_positives(
        self,
    ) -> None:
        for case in (2, 3):
            with self.subTest(case=case):
                self.assertTrue(self.run_case(self.original, case))

    def test_patched_native_predicate_preserves_signal_protection(self) -> None:
        for case, protected in enumerate(
            (False, False, False, False, True, False, True, False, True, False)
        ):
            with self.subTest(case=case):
                self.assertEqual(self.run_case(self.patched, case), protected)


if __name__ == "__main__":
    unittest.main()

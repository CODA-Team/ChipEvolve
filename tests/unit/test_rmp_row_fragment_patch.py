"""Compile the original and patched native projection against row fragments."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class RmpRowFragmentPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        project = Path(__file__).resolve().parents[2]
        fixture = project / "tests/fixtures/rmp_original_row_projection.cc"
        harness = (project / "tests/fixtures/rmp_row_projection_harness.cc").read_text()
        compiler = shutil.which("c++")
        if compiler is None:
            raise RuntimeError("C++ compiler is required for native row regression")
        target = cls.root / "src/cut/src/blif.cpp"
        target.parent.mkdir(parents=True)
        target.write_text(fixture.read_text())
        patch = project / "toolchain/patches/fix-rmp-row-fragment-projection.patch"
        subprocess.run(
            ["git", "apply", "--check", str(patch)], cwd=cls.root, check=True
        )
        subprocess.run(["git", "apply", str(patch)], cwd=cls.root, check=True)
        cls.original = cls.root / "original"
        cls.patched = cls.root / "patched"
        for binary, projection in (
            (cls.original, fixture.read_text()),
            (cls.patched, target.read_text()),
        ):
            source = binary.with_suffix(".cc")
            source.write_text(
                harness.replace("// INSERT_EXACT_NATIVE_PROJECTION", projection)
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

    def run_case(self, binary: Path, case: int) -> tuple[int, ...]:
        result = subprocess.run(
            [str(binary), str(case)], text=True, capture_output=True, check=True
        )
        return tuple(map(int, result.stdout.split()))

    def test_original_displaces_legal_cells_or_accepts_too_narrow_fragment(
        self,
    ) -> None:
        for case, actual in (
            (1, (1, 80, 0, 0)),
            (2, (1, 80, 0, 0)),
            (3, (1, 0, 0, 0)),
            (4, (1, 0, 0, 0)),
            (13, (1, 200, 0, 0)),
        ):
            with self.subTest(case=case):
                self.assertEqual(self.run_case(self.original, case), actual)

    def test_patched_projection_preserves_grid_and_chooses_fitting_fragment(
        self,
    ) -> None:
        no_row = (0, -999, -999, 0)
        expected = (
            (1, 50, 0, 0),
            (1, 250, 0, 0),
            (1, 250, 10, 1),
            (1, 220, 0, 0),
            no_row,
            (1, 220, 0, 0),
            no_row,
            (1, -10, 0, 0),
            (1, 50, 0, 0),
            (1, 50, 0, 0),
            (1, 100, 0, 0),
            no_row,
            no_row,
            (1, 50, 0, 0),
        )
        for case, projection in enumerate(expected):
            with self.subTest(case=case):
                self.assertEqual(self.run_case(self.patched, case), projection)
                if case not in (1, 2, 3, 4, 13):
                    self.assertEqual(self.run_case(self.original, case), projection)


if __name__ == "__main__":
    unittest.main()

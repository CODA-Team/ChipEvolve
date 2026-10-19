"""A copied GNU archive must not resolve the previous candidate's object."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from goalevolve.evaluation.contest2026 import Contest2026OpenROADEvaluator


class StaticArchiveToolchainTests(unittest.TestCase):
    def test_current_compiler_archivers_replace_previous_object(self):
        ar = shutil.which("ar")
        self.assertIsNotNone(ar, "GNU ar is needed to verify actual archive semantics")
        assert ar is not None
        for name in ("ar", "gcc-ar", "gcc-ar-11", "llvm-ar", "llvm-ar-18"):
            with (
                self.subTest(archiver=name),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                obj = root / "policy.o"
                archive = root / "libpolicy.a"
                script = root / "link.txt"
                obj.write_bytes(b"previous policy")
                subprocess.run([ar, "qc", str(archive), str(obj)], check=True)
                obj.write_bytes(b"current source policy")
                script.write_text(f'"/usr/bin/{name}" qc libpolicy.a policy.o\n')
                Contest2026OpenROADEvaluator._remove_stale_static_archive(
                    link_script=script, cwd=root
                )
                subprocess.run([ar, "qc", str(archive), str(obj)], check=True)
                members = subprocess.check_output([ar, "t", str(archive)], text=True)
                selected = subprocess.check_output([ar, "p", str(archive), "policy.o"])
                self.assertEqual(members.splitlines(), ["policy.o"])
                self.assertEqual(selected, b"current source policy")


if __name__ == "__main__":
    unittest.main()

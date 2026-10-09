"""Exercise evidence capture/restore boundaries with temporary synthetic files."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from build_evidence_delivery import capture, restore, verify


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejects(call):
    try:
        call()
    except (ValueError, OSError):
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Acceptance records are immutable")
    checks = []

    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})

    with tempfile.TemporaryDirectory(prefix="eda-evidence-acceptance-") as directory:
        root = Path(directory)
        source = root / "source"
        source.mkdir()
        (source / "trace-a.json").write_text("{}\n")
        (source / "trace-b.json").write_text("{}\n")
        (source / "a.odb").write_bytes(b"same-native-input")
        (source / "b.odb").write_bytes(b"same-native-input")
        original = root / "original.rpt"
        original.write_text("native oracle\n")
        locator = {
            "run-a/art-report": {
                "locator": {
                    "path": str(original),
                    "sha256": sha(original),
                    "size_bytes": original.stat().st_size,
                }
            }
        }
        bundle = root / "bundle"
        manifest = capture({"sprint": source}, bundle, 100, locator)
        files = {row["logical_path"]: row for row in manifest["files"]}
        check("duplicate_blobs_deduplicated", manifest["unique_blobs"] == 2)
        check(
            "registered_original_captured",
            files["registered-originals/run-a/art-report"]["sha256"] == sha(original),
        )
        check(
            "native_inputs_explicit_external",
            files["sprint/a.odb"]["storage"] == "external_dependency",
        )
        check(
            "external_logical_and_unique_bytes_distinct",
            manifest["external_dependency_bytes"] == 2 * len(b"same-native-input")
            and manifest["unique_external_content_bytes"] == len(b"same-native-input"),
        )
        check(
            "full_verification",
            verify(bundle, True)["external_dependencies_verified"] == 2,
        )
        restore(bundle, root / "restore")
        check(
            "original_report_restored",
            (root / "restore/registered-originals/run-a/art-report").read_bytes()
            == original.read_bytes(),
        )
        check(
            "external_not_silently_copied",
            not (root / "restore/sprint/a.odb").exists()
            and (root / "restore/external-dependencies.json").is_file(),
        )
        native = source / "a.odb"
        native.write_bytes(b"changed-native-input")
        check("external_mutation_detected", rejects(lambda: verify(bundle, True)))
        native.write_bytes(b"same-native-input")
        blob = bundle / "blobs" / files["sprint/trace-a.json"]["sha256"]
        blob.write_bytes(b"bad\n")
        check("blob_mutation_detected", rejects(lambda: verify(bundle)))
        blob.write_bytes(b"{}\n")
        manifest_path = bundle / "manifest.json"
        saved_manifest = manifest_path.read_bytes()
        manifest_path.write_bytes(saved_manifest + b" ")
        check("manifest_mutation_detected", rejects(lambda: verify(bundle)))
        manifest_path.write_bytes(saved_manifest)
        bad_expected = {
            "run-a/art-report": {
                "locator": {
                    "path": str(original),
                    "sha256": "0" * 64,
                    "size_bytes": original.stat().st_size,
                }
            }
        }
        check(
            "expected_original_hash_mismatch_rejected",
            rejects(
                lambda: capture(
                    {"sprint": source}, root / "bad-hash", 100, bad_expected
                )
            ),
        )
        check(
            "unresolved_original_rejected",
            rejects(
                lambda: capture(
                    {"sprint": source}, root / "unresolved", 100, {"run-a/art": {}}
                )
            ),
        )
        check(
            "unsafe_original_identity_rejected",
            rejects(
                lambda: capture(
                    {"sprint": source},
                    root / "unsafe",
                    100,
                    {"../escape": locator["run-a/art-report"]},
                )
            ),
        )
        secret = root / "secret-source"
        secret.mkdir()
        (secret / "fixture.txt").write_text("sk" + "-" + "A" * 30)
        check(
            "credential_literal_rejected",
            rejects(lambda: capture({"sprint": secret}, root / "secret", 100)),
        )
        linked = root / "linked-source"
        linked.mkdir()
        (linked / "alias").symlink_to(original)
        check(
            "symlink_rejected",
            rejects(lambda: capture({"sprint": linked}, root / "linked", 100)),
        )
        clean = root / "clean"
        clean.mkdir()
        image = root / "orfs.sif"
        image.write_bytes(b"synthetic-toolchain")
        freeze = root / "freeze.json"
        freeze.write_text(
            json.dumps({"toolchain": {"image": str(image), "sha256": sha(image)}})
        )
        builder = Path(__file__).with_name("build_evidence_delivery.py")

        def build(output):
            return subprocess.run(
                [
                    sys.executable,
                    str(builder),
                    "build",
                    "--sprint",
                    str(source),
                    "--clean-evidence",
                    str(clean),
                    "--toolchain-freeze",
                    str(freeze),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )

        check("toolchain_image_build", build(root / "with-toolchain").returncode == 0)
        tool_manifest = json.loads((root / "with-toolchain/manifest.json").read_text())
        check(
            "toolchain_explicit_external_identity",
            any(
                row["logical_path"] == "registered-originals/toolchain/orfs-image"
                and row["storage"] == "external_dependency"
                and row["sha256"] == sha(image)
                for row in tool_manifest["files"]
            ),
        )
        freeze.write_text(
            json.dumps({"toolchain": {"image": str(image), "sha256": "0" * 64}})
        )
        check(
            "toolchain_hash_mismatch_rejected",
            build(root / "wrong-toolchain").returncode != 0,
        )
        check(
            "capture_root_output_rejected",
            build(source / "nested-bundle").returncode != 0,
        )
    result = {
        "passed": all(row["passed"] for row in checks),
        "checks": checks,
        "program_sha256": sha(Path(__file__)),
        "builder_sha256": sha(builder),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "checks": len(checks),
                "output": str(args.output),
            }
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

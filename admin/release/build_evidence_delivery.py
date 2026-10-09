"""Capture finalized evidence as deduplicated blobs with explicit dependencies.

Large native inputs and databases remain in their original locations. Their
bytes are hashed and listed as external dependencies, never silently omitted.
The package can be verified/restored without importing any product parser.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil


SECRET_LITERAL = re.compile(rb"(?:sk-(?:or-v1-)?[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16})")
NATIVE_SUFFIXES = {
    ".odb",
    ".sif",
    ".lib",
    ".spef",
    ".lef",
    ".gds",
    ".sqlite",
    ".db",
    ".whl",
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def identity(stat):
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def storage_for(relative, path, max_blob_bytes):
    if (
        path.suffix.lower() in NATIVE_SUFFIXES
        or ".sqlite" in path.name
        or path.stat().st_size > max_blob_bytes
        or ("runtime-workspaces" in relative.parts and "inputs" in relative.parts)
    ):
        return "external_dependency"
    return "blob"


def capture(roots, output, max_blob_bytes, originals=None):
    output.mkdir(parents=True, exist_ok=False)
    blobs = output / "blobs"
    blobs.mkdir()
    records = []

    def inputs():
        for label, root in roots.items():
            if not root.is_dir():
                raise ValueError("Evidence root does not exist: " + str(root))
            for directory, dirs, names in os.walk(root, followlinks=False):
                dirs.sort()
                for name in sorted(dirs):
                    if (Path(directory) / name).is_symlink():
                        raise ValueError(
                            "Evidence directory symlink requires explicit treatment"
                        )
                for name in sorted(names):
                    path = Path(directory) / name
                    yield label, path.relative_to(root), path, None
        for key, original in sorted((originals or {}).items()):
            relative = Path(key)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or len(relative.parts) != 2
            ):
                raise ValueError("Invalid registered original identity")
            locator = original.get("locator")
            if not locator:
                raise ValueError("Unresolved registered original: " + key)
            path = Path(locator["path"])
            yield "registered-originals", relative, path, locator

    for label, relative, path, expected in inputs():
        if path.is_symlink() or not path.is_file():
            raise ValueError(
                "Evidence symlink/non-file requires explicit treatment: " + str(path)
            )
        before = path.stat()
        storage = storage_for(relative, path, max_blob_bytes)
        hasher = hashlib.sha256()
        temporary = output / ".capture.tmp"
        sink = temporary.open("wb") if storage == "blob" else None
        carry = b""
        try:
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1048576), b""):
                    hasher.update(block)
                    if sink:
                        if SECRET_LITERAL.search(carry + block):
                            raise ValueError(
                                "Potential credential literal in evidence; file excluded from publication: "
                                + str(path)
                            )
                        sink.write(block)
                        carry = block[-128:]
        finally:
            if sink:
                sink.close()
        if identity(before) != identity(path.stat()):
            raise ValueError("Evidence changed during capture: " + str(path))
        sha = hasher.hexdigest()
        if expected and (
            sha != expected["sha256"] or before.st_size != expected["size_bytes"]
        ):
            raise ValueError(
                "Registered original differs from its locator receipt: " + str(path)
            )
        blob = blobs / sha
        if storage == "blob":
            if blob.exists():
                temporary.unlink()
            else:
                temporary.replace(blob)
        records.append(
            {
                "logical_path": label + "/" + relative.as_posix(),
                "source_path": str(path.resolve()),
                "sha256": sha,
                "size_bytes": before.st_size,
                "storage": storage,
            }
        )
    manifest = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "builder_sha256": digest(Path(__file__)),
        "roots": {label: str(path.resolve()) for label, path in roots.items()},
        "files": records,
        "storage_counts": dict(Counter(row["storage"] for row in records)),
        "unique_blobs": len(list(blobs.iterdir())),
        "blob_size_bytes": sum(path.stat().st_size for path in blobs.iterdir()),
        "external_dependency_bytes": sum(
            row["size_bytes"]
            for row in records
            if row["storage"] == "external_dependency"
        ),
        "unique_external_content_bytes": sum(
            size
            for _, size in {
                (row["sha256"], row["size_bytes"])
                for row in records
                if row["storage"] == "external_dependency"
            }
        ),
        "external_bytes_note": "external_dependency_bytes counts logical references, including repeated identical inputs; unique_external_content_bytes counts unique hash/size pairs, not allocated filesystem blocks.",
        "limits": "External dependencies require the same server or separately supplied identical bytes. Captured raw traces are evidence, not successful grades. No RC verdict is inferred.",
    }
    target = output / "manifest.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    (output / "manifest.sha256").write_text(digest(target) + "  manifest.json\n")
    return manifest


def verify(bundle, external=False):
    manifest_path = bundle / "manifest.json"
    if digest(manifest_path) != (bundle / "manifest.sha256").read_text().split()[0]:
        raise ValueError("Manifest digest mismatch")
    manifest = json.loads(manifest_path.read_text())
    blobs = {
        row["sha256"]: row["size_bytes"]
        for row in manifest["files"]
        if row["storage"] == "blob"
    }
    for sha, size in blobs.items():
        path = bundle / "blobs" / sha
        if path.stat().st_size != size or digest(path) != sha:
            raise ValueError("Blob verification failed: " + sha)
    dependencies = [
        row for row in manifest["files"] if row["storage"] == "external_dependency"
    ]
    if external:
        for row in dependencies:
            path = Path(row["source_path"])
            if (
                path.stat().st_size != row["size_bytes"]
                or digest(path) != row["sha256"]
            ):
                raise ValueError(
                    "External dependency verification failed: " + str(path)
                )
    return {
        "unique_blobs_verified": len(blobs),
        "external_dependencies": len(dependencies),
        "external_dependencies_verified": len(dependencies) if external else 0,
        "external_verification_status": "passed" if external else "not_run",
        "blob_verification_passed": True,
    }


def restore(bundle, target):
    verify(bundle)
    target.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((bundle / "manifest.json").read_text())
    for row in manifest["files"]:
        if row["storage"] != "blob":
            continue
        relative = Path(row["logical_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe logical evidence path")
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundle / "blobs" / row["sha256"], path)
    (target / "external-dependencies.json").write_text(
        json.dumps(
            [
                row
                for row in manifest["files"]
                if row["storage"] == "external_dependency"
            ],
            indent=2,
        )
        + "\n"
    )


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--sprint", type=Path, required=True)
    build.add_argument("--clean-evidence", type=Path, required=True)
    build.add_argument(
        "--extra-root", action="append", default=[], metavar="LABEL=PATH"
    )
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--original-locators", type=Path)
    build.add_argument("--toolchain-freeze", type=Path)
    build.add_argument("--max-blob-bytes", type=int, default=100_000_000)
    check = sub.add_parser("verify")
    check.add_argument("--bundle", type=Path, required=True)
    check.add_argument("--external", action="store_true")
    expand = sub.add_parser("restore")
    expand.add_argument("--bundle", type=Path, required=True)
    expand.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        roots = {
            "sprint": args.sprint.resolve(),
            "clean": args.clean_evidence.resolve(),
        }
        for extra in args.extra_root:
            label, separator, path = extra.partition("=")
            if (
                not separator
                or not re.fullmatch(r"[A-Za-z0-9_-]+", label)
                or label in roots
                or label == "registered-originals"
            ):
                raise ValueError(
                    "Extra roots need a unique safe label and an explicit path"
                )
            roots[label] = Path(path).resolve()
        if any(
            root == args.output.resolve() or root in args.output.resolve().parents
            for root in roots.values()
        ):
            raise ValueError("Bundle output must be outside captured evidence roots")
        originals = (
            json.loads(args.original_locators.read_text())
            if args.original_locators
            else None
        )
        if args.toolchain_freeze:
            toolchain = json.loads(args.toolchain_freeze.read_text())["toolchain"]
            path = Path(toolchain["image"])
            originals = dict(originals or {})
            key = "toolchain/orfs-image"
            if key in originals:
                raise ValueError(
                    "Toolchain identity collides with a registered original"
                )
            originals[key] = {
                "locator": {
                    "path": str(path),
                    "sha256": toolchain["sha256"],
                    "size_bytes": path.stat().st_size,
                }
            }
        manifest = capture(roots, args.output.resolve(), args.max_blob_bytes, originals)
        print(
            json.dumps(
                {
                    key: manifest[key]
                    for key in (
                        "storage_counts",
                        "unique_blobs",
                        "blob_size_bytes",
                        "external_dependency_bytes",
                    )
                }
            )
        )
    elif args.command == "verify":
        print(json.dumps(verify(args.bundle, args.external)))
    else:
        restore(args.bundle, args.output)
        print(
            json.dumps(
                {
                    "restored_to": str(args.output.resolve()),
                    "external_dependencies_copied": False,
                }
            )
        )


if __name__ == "__main__":
    main()

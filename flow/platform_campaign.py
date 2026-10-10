"""Phase commits for the native controller; physical bytes stay in EF archives."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from llm_usage import _calls, load_events
from platform_execution import digest, find_predecessor, project_archive, write_record
from platform_model import process_identity


def settings():
    return json.loads(Path(os.environ["DRP_PLATFORM_CONFIG"]).read_text())


def root():
    return Path(settings()["state_root"]).resolve()


def fingerprint(flow):
    source = flow.parent
    names = (
        subprocess.check_output(["git", "ls-files", "-z"], cwd=source)
        .decode()
        .split("\0")
    )
    files = {
        name: digest(source / name)
        for name in names
        if name and (source / name).is_file()
    }
    for name in ("config/env.local.sh",):
        if (source / name).is_file():
            files[name] = digest(source / name)
    profile_path = Path(settings()["profile_path"])
    profile = json.loads(profile_path.read_text())
    tools = {
        name: digest(Path(profile[name])) for name in ("openroad_bin", "yosys_bin")
    }
    packages = sorted(
        [row.metadata["Name"], row.version]
        for row in importlib.metadata.distributions()
    )
    return {
        "files": files,
        "profile": digest(profile_path),
        "tools": tools,
        "packages": packages,
        "settings": settings(),
        "options": os.environ["DRP_CAMPAIGN_OPTIONS"],
        "transport": os.environ.get("DRP_LLM_TRANSPORT", "api"),
        "min_success": os.environ.get("MIN_SUCCESS"),
        "interpreter": os.path.realpath(sys.executable),
    }


def assert_old_group_stopped(owner):
    # The CLI model uses a separate session and is audited independently by the
    # response cache. This check covers native leaf publishers and stage workers.
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            row = process_identity(int(path.name))
        except ProcessLookupError:
            continue
        if (
            row
            and row["process_group"] == owner["process_group"]
            and row["state"] != "Z"
        ):
            raise RuntimeError(
                "The previous campaign process group still has live workers."
            )


def small_files(flow, platform, design):
    design_root = flow / "designs" / platform / design
    paths = [
        p
        for p in design_root.iterdir()
        if p.is_file() and p.suffix in {".mk", ".sdc", ".txt", ".csv", ".json"}
    ]
    paths += [
        p
        for p in (flow / "tmp").rglob("*")
        if p.is_file() and p.suffix in {".json", ".csv", ".txt"}
    ]
    paths += list((flow / "logs").glob(f"{platform}_{design}_run*.log"))
    paths += list((flow / "logs").glob("eval_tns_*_run*.log"))
    return sorted(set(paths))


def physical_refs(flow, state, campaign, iteration, platform, design, runs):
    refs = []
    for slot in range(1, runs + 1):
        results = flow / "results" / platform / design / f"run_{slot}"
        for stem, next_stage in [
            ("6_final", "eval_final"),
            ("4_cts", "route_finish"),
            ("3_place", "cts"),
        ]:
            if (results / (stem + ".odb")).is_file():
                record = find_predecessor(
                    state, flow, campaign, iteration, platform, design, slot, next_stage
                )
                archive = next(
                    row for row in record["artifacts"] if row["kind"] == "flow_archive"
                )
                path = (
                    state
                    / f"iteration-{iteration}/slot-{record['candidate_slot']}-{record['stage']}.zip"
                )
                if digest(path) != archive["sha256"]:
                    raise RuntimeError("The retained physical archive changed.")
                refs.append(
                    {
                        "slot": slot,
                        "run_id": record["run_id"],
                        "archive": archive,
                        "path": str(path),
                        "odb_sha256": digest(results / (stem + ".odb")),
                        "sdc_sha256": digest(results / (stem + ".sdc")),
                        "stem": stem,
                    }
                )
                break
    return refs


def commit(flow, state, iteration, phase):
    journal_path = state / "campaign.json"
    journal = json.loads(journal_path.read_text())
    platform, design = journal["platform"], journal["design"]
    checkpoint = (
        state / "checkpoints" / f"iteration-{iteration}-phase-{phase}-{time.time_ns()}"
    )
    if checkpoint.exists():
        raise RuntimeError("Refusing to overwrite a published phase checkpoint.")
    temporary = checkpoint.with_name("." + checkpoint.name + "-" + str(os.getpid()))
    temporary.mkdir(parents=True)
    files, dumps = {}, {}
    backup = flow / "backup_dir" / platform / design
    dump_paths = [
        p
        for directory in backup.glob("result_dump_*")
        if directory.is_dir()
        for p in directory.rglob("*")
        if p.is_file()
    ]
    # One small archive gives a bounded durability operation per phase. Physical
    # ODB/GDS never enters this archive; its registered EF producer is referenced.
    with zipfile.ZipFile(
        temporary / "native-state.zip", "w", zipfile.ZIP_DEFLATED
    ) as archive:
        for paths, hashes in [
            (small_files(flow, platform, design), files),
            (dump_paths, dumps),
        ]:
            for path in paths:
                relative = str(path.relative_to(flow))
                archive.write(path, relative)
                hashes[relative] = digest(path)
    physical = (
        physical_refs(
            flow,
            state,
            journal["campaign_id"],
            iteration,
            platform,
            design,
            journal["runs"],
        )
        if phase >= 1
        else []
    )
    receipt = {
        "iteration": iteration,
        "phase": phase,
        "files": files,
        "dumps": dumps,
        "physical": physical,
        "campaign_id": journal["campaign_id"],
        "time": time.time(),
        "state_archive_sha256": digest(temporary / "native-state.zip"),
    }
    with (temporary / "native-state.zip").open("rb") as stream:
        os.fsync(stream.fileno())
    write_record(temporary / "receipt.json", receipt)
    os.rename(temporary, checkpoint)
    journal.update(
        iteration=iteration,
        phase=phase,
        checkpoint=str(checkpoint),
        checkpoint_sha256=digest(checkpoint / "receipt.json"),
    )
    write_record(journal_path, journal)
    print(f"[platform] committed iteration={iteration} phase={phase}", flush=True)
    # An explicit acceptance gate permits external termination at a real commit.
    # No synthetic EDA work is substituted, and the gate is never enabled by default.
    gate = os.environ.get("DRP_ACCEPTANCE_GATE")
    if gate == f"{iteration}:{phase}":
        write_record(
            state / "acceptance-gate.json",
            {"iteration": iteration, "phase": phase, "owner": journal["owner"]},
        )
        while not (state / "release-acceptance-gate").exists():
            time.sleep(0.2)


def restore(flow, state, journal):
    checkpoint = Path(journal["checkpoint"])
    if digest(checkpoint / "receipt.json") != journal["checkpoint_sha256"]:
        raise RuntimeError("Published checkpoint receipt changed.")
    receipt = json.loads((checkpoint / "receipt.json").read_text())
    archive_path = checkpoint / "native-state.zip"
    if digest(archive_path) != receipt["state_archive_sha256"]:
        raise RuntimeError("Published native state archive changed.")
    with zipfile.ZipFile(archive_path) as archive:
        content = {
            name: archive.read(name)
            for name in {**receipt["files"], **receipt["dumps"]}
        }
    for relative, sha in {**receipt["files"], **receipt["dumps"]}.items():
        if hashlib.sha256(content[relative]).hexdigest() != sha:
            raise RuntimeError("Published checkpoint bytes changed: " + relative)
    platform, design = journal["platform"], journal["design"]
    backup = flow / "backup_dir" / platform / design
    committed_iteration = (
        journal["iteration"] if journal["phase"] == 7 else journal["iteration"] - 1
    )
    for directory in backup.glob("result_dump_*"):
        number = int(directory.name.rsplit("_", 1)[1])
        if number <= committed_iteration:
            expected = {
                name: sha
                for name, sha in receipt["dumps"].items()
                if name.startswith(str(directory.relative_to(flow)) + "/")
            }
            actual = {
                str(p.relative_to(flow)): digest(p)
                for p in directory.rglob("*")
                if p.is_file()
            }
            if actual != expected:
                raise RuntimeError("An immutable completed iteration dump changed.")
        else:
            preserved = (
                state / "interrupted-dumps" / str(time.time_ns()) / directory.name
            )
            preserved.parent.mkdir(parents=True)
            shutil.move(directory, preserved)
    for path in small_files(flow, platform, design):
        path.unlink()
    for name in ("results", "logs", "objects", "reports"):
        for directory in (flow / name / platform / design).glob("run_*"):
            shutil.rmtree(directory)
    for ref in receipt["physical"]:
        archive = Path(ref["path"])
        if digest(archive) != ref["archive"]["sha256"]:
            raise RuntimeError("Physical archive bytes changed before restore.")
        project_archive(archive, flow, platform, design, ref["slot"])
        results = flow / "results" / platform / design / f"run_{ref['slot']}"
        if (
            digest(results / (ref["stem"] + ".odb")) != ref["odb_sha256"]
            or digest(results / (ref["stem"] + ".sdc")) != ref["sdc_sha256"]
        ):
            raise RuntimeError(
                "Restored physical checkpoint differs from the committed donor."
            )
    for relative in {**receipt["files"], **receipt["dumps"]}:
        destination = flow / relative
        if relative in receipt["dumps"] and destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content[relative])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["root", "preflight", "begin", "resume", "commit"]
    )
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--phase", type=int)
    args = parser.parse_args()
    state = root()
    flow = Path(__file__).resolve().parent
    if args.command == "root":
        print(state)
        return
    journal_path = state / "campaign.json"
    if args.command in {"preflight", "resume"}:
        journal = json.loads(journal_path.read_text())
        backup = flow / "backup_dir" / journal["platform"] / journal["design"]
        if digest(backup / "campaign_manifest.json") != journal["manifest_sha256"]:
            raise RuntimeError("The original campaign manifest changed.")
        _calls(load_events(backup / "llm_usage_events.jsonl"), journal["campaign_id"])
        if journal["fingerprint"] != fingerprint(flow):
            raise RuntimeError(
                "Campaign options, source, tools or installed environment changed."
            )
        if args.command == "preflight":
            assert_old_group_stopped(journal["owner"])
        else:
            restore(flow, state, journal)
            journal["owner"] = process_identity(os.getppid())
            journal["resume_count"] = journal.get("resume_count", 0) + 1
            write_record(journal_path, journal)
            iteration, phase = journal["iteration"], journal["phase"]
            print(
                f"{iteration + 1 if phase == 7 else iteration}|{-1 if phase == 7 else phase}|"
                f"{iteration if phase == 7 else iteration - 1}|{journal['campaign_id']}"
            )
        return
    if args.command == "begin":
        if journal_path.exists():
            raise RuntimeError(
                "State root already owns a campaign; use --resume or a new state root."
            )
        journal = {
            "campaign_id": os.environ["DRP_CAMPAIGN_ID"],
            "platform": os.environ["PLATFORM"],
            "design": os.environ["DESIGN"],
            "runs": int(os.environ["PARALLEL_RUNS"]),
            "fingerprint": fingerprint(flow),
            "owner": process_identity(os.getppid()),
            "manifest_sha256": digest(
                flow
                / "backup_dir"
                / os.environ["PLATFORM"]
                / os.environ["DESIGN"]
                / "campaign_manifest.json"
            ),
            "resume_count": 0,
        }
        write_record(journal_path, journal)
        commit(flow, state, 1, -1)
    else:
        commit(flow, state, args.iteration, args.phase)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Campaign state + auto-invalidation for DRP-Agent derived files.

The derived-state files below are all a function of the BASELINE run (the default
config's flow result) plus the objective:

    cp0.txt, tns_base.txt, power_base.txt   (CP_0 / |TNS| / power reference)
    baseline_trajectory.csv, baseline_trajectory.meta.json, baseline_best.txt
                                                    (QoR-comparator baseline)
    optimization_state.json, <platform>_<design>.csv (committed next-batch contract)

When the design / objective / base config changes they go stale, and forgetting to
delete them is a recurring footgun (e.g. a stale CP_0 or the wrong baseline). This
module records a campaign FINGERPRINT in one `designs/<p>/<d>/state.json` and clears
the derived files automatically whenever the fingerprint changes (or on --fresh).

Usage (from maindriver):
    python3 state.py invalidate <platform> <design> <objective> [--fresh]
"""
import hashlib
import json
import sys
from pathlib import Path

DERIVED_FILES = [
    "cp0.txt", "tns_base.txt", "power_base.txt",
    "baseline_trajectory.csv", "baseline_trajectory.meta.json",
    "baseline_best.txt", "optimization_state.json",
]
_LIVE_CAMPAIGN_ARTIFACTS = (
    "campaign_manifest.json",
    "llm_usage_events.jsonl",
    "llm_usage_summary.json",
)


def _design_dir(platform: str, design: str) -> Path:
    return Path(__file__).parent / "designs" / platform / design


def _tmp_dir() -> Path:
    return Path(__file__).parent / "tmp"


def _backup_design_dir(platform: str, design: str) -> Path:
    return Path(__file__).parent / "backup_dir" / platform / design


# Per-iteration campaign temp files. Left behind by a previous campaign they produce
# the "triangle contamination": result_dump_1 of the NEW campaign archives the OLD
# campaign's iter2..N jsons until the new campaign has overwritten them all.
_TMP_CAMPAIGN_GLOBS = [
    "metrics_place_iter*.json", "metrics_cts_iter*.json", "metrics_final_iter*.json",
    "drp_place_iter*.json", "drp_cts_iter*.json",
    "lineage_iter*.json",
    "config_replay_iter*.json",
    "candidate_lifecycle_iter*.json",
    "cts_params.json", "routing_params.json", "*_params_provenance.json",
    "sorted_metrics_*.json",
]


def campaign_key(platform: str, design: str, objective: str,
                 weight_wl: str = "", weight_ecp: str = "",
                 power_budget: str = "") -> str:
    """Fingerprint of everything that, if changed, makes the derived state stale:
    platform/design/objective + the base config.mk and constraint.sdc content, plus
    the objective's tuning knobs — combo weights (rescale combo) and, for TNS_EVAL, the
    power_budget (changes which runs are feasible, so a stale baseline_best.txt would be
    compared against a differently-constrained objective)."""
    parts = [platform, design, objective]
    if objective == "combo":
        parts += [str(weight_wl), str(weight_ecp)]
    if objective == "TNS_EVAL":
        parts += [str(power_budget)]
    d = _design_dir(platform, design)
    for fname in ("config.mk", "constraint.sdc"):
        p = d / fname
        parts.append(p.read_text() if p.exists() else "")
    return hashlib.md5("\x00".join(parts).encode()).hexdigest()


def invalidate_if_stale(platform: str, design: str, objective: str,
                        weight_wl: str = "", weight_ecp: str = "",
                        power_budget: str = "", force: bool = False):
    """Clear derived files if the campaign fingerprint changed (or force). Rewrites
    state.json with the current fingerprint. Returns (cleared_files, reason)."""
    d = _design_dir(platform, design)
    state_path = d / "state.json"
    key = campaign_key(platform, design, objective, weight_wl, weight_ecp, power_budget)

    old = None
    if state_path.exists():
        try:
            old = json.loads(state_path.read_text()).get("campaign_key")
        except Exception:
            old = None

    if not force and old == key:
        return [], "unchanged"

    cleared = []
    failed = []
    # TextGrad-persisted agent instructions are campaign state too: stale directives
    # (e.g. a 'clk_period>=500' written under an old objective) must not leak into a
    # new campaign and steer its sampling.
    targets = [d / fname for fname in DERIVED_FILES]
    # The generated parameter CSV and optimization_state form one batch contract.
    # Clearing only the state leaves an orphaned old batch visible until Phase 0.
    targets.append(d / f"{platform}_{design}.csv")
    targets.append(_tmp_dir() / f"agentic_prompts_{platform}_{design}.json")
    # Per-iteration tmp jsons from the previous campaign (see _TMP_CAMPAIGN_GLOBS).
    for pat in _TMP_CAMPAIGN_GLOBS:
        targets.extend(sorted(_tmp_dir().glob(pat)))

    # Archive (move, don't delete) the previous campaign's result_dump_* so the new
    # campaign starts with an empty backup tree and old experiments stay browsable
    # under backup_dir/<p>/<d>/campaign_<UTC-stamp>/.
    bdir = _backup_design_dir(platform, design)
    old_dumps = sorted(bdir.glob("result_dump_*")) if bdir.exists() else []
    old_artifacts = [
        bdir / name for name in _LIVE_CAMPAIGN_ARTIFACTS
        if (bdir / name).exists()
    ]
    if old_dumps or old_artifacts:
        import datetime
        stamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        # A second -F within the same second must not merge with or overwrite the
        # first archive. Pick a fresh suffix instead of reusing an existing directory.
        arch = bdir / f"campaign_{stamp}"
        suffix = 0
        while arch.exists():
            suffix += 1
            arch = bdir / f"campaign_{stamp}_{suffix:02d}"
        arch.mkdir(parents=True, exist_ok=False)
        moved_artifacts = []
        for artifact in old_artifacts:
            try:
                artifact.rename(arch / artifact.name)
                moved_artifacts.append(artifact.name)
            except Exception as e:
                print(f"[state][ERROR] cannot archive {artifact.name}: {e}",
                      file=sys.stderr)
                failed.append(artifact.name)
        moved = 0
        for dump in old_dumps:
            try:
                dump.rename(arch / dump.name)
                moved += 1
            except Exception as e:
                print(f"[state][ERROR] cannot archive {dump}: {e}", file=sys.stderr)
                failed.append(dump.name)
        if moved:
            cleared.append(f"archived {moved} result_dump_* -> {arch.name}/")
        if moved_artifacts:
            cleared.append(
                f"archived {', '.join(moved_artifacts)} -> {arch.name}/"
            )
    for p in targets:
        if p.exists():
            try:
                p.unlink()
                cleared.append(p.name)
            except Exception as e:
                print(f"[state][ERROR] cannot delete {p}: {e}", file=sys.stderr)
            if p.exists():   # unlink 'succeeded' but file persists, or failed above
                failed.append(p.name)

    # HARD FAILURE on incomplete clearing: registering the new campaign_key while a
    # stale file survived would make every later start report 'unchanged' and silently
    # run on an old CP_0/baseline — exactly the footgun this module exists to kill.
    # Leave state.json untouched so the next start retries the clear.
    if failed:
        raise RuntimeError(
            f"stale derived state NOT fully cleared ({failed}); campaign fingerprint "
            f"not updated — fix permissions/locks and re-run.")

    d.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({
        "platform": platform, "design": design, "objective": objective,
        "campaign_key": key,
    }, indent=2))
    reason = "forced" if force else ("new campaign" if old is None else "campaign changed")
    return cleared, reason


def main():
    if len(sys.argv) >= 5 and sys.argv[1] == "invalidate":
        platform, design, objective = sys.argv[2], sys.argv[3], sys.argv[4]
        pos = [a for a in sys.argv[5:] if not a.startswith("--")]  # weight_wl, weight_ecp, power_budget
        weight_wl = pos[0] if len(pos) > 0 else ""
        weight_ecp = pos[1] if len(pos) > 1 else ""
        power_budget = pos[2] if len(pos) > 2 else ""
        force = "--fresh" in sys.argv[5:]
        try:
            cleared, reason = invalidate_if_stale(platform, design, objective,
                                                  weight_wl, weight_ecp, power_budget,
                                                  force)
        except RuntimeError as e:
            print(f"[state][ERROR] {e}", file=sys.stderr)
            sys.exit(1)   # maindriver aborts (no silent run on stale state)
        if cleared:
            print(f"[state] {reason}: cleared stale derived state {cleared}")
        else:
            print(f"[state] {reason}: derived state kept")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()

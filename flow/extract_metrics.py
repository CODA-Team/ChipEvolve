#!/usr/bin/env python3
"""
Stage-aware metrics extraction for DRP-Agent.

Extracts wirelength (wl), effective clock period (ecp), and combo metrics
from OpenROAD flow logs at different stages: placement, cts, final.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Regex patterns for different stages
# ---------------------------------------------------------------------------

# Placement stage: HPWL from the global-placement convergence table.
# Table rows look like:
#   "  451 |   0.0995 |  4.840151e+04 |          |  2.29e-05 |"
# Columns: Iteration | Overflow | HPWL (um) | HPWL(%) | Penalty | Group
# The 3rd column is HPWL in um; the last matching row is the final global-place
# wirelength. (The old "[INFO GPL-NNNN] HPWL: <num>" form never appears — that
# log line is only a header: "[INFO GPL-0031] HPWL: Half-Perimeter Wirelength".)
#   col1=Iteration  col2=Overflow  col3=HPWL(um)  col4=HPWL(%)  col5=Penalty
# The Penalty column (col5) is always scientific notation (e.g. 2.29e-05); CTS
# and routing tables use the pipe format too, so we anchor on that scientific
# 5th column to match ONLY global-placement rows. The combined log accumulates
# all stages, so this specificity is required to avoid grabbing a later table.
HPWL_PATTERN = re.compile(
    r'^\s*\d+\s*\|\s*[\d.]+\s*\|\s*([\d.eE+\-]+)\s*\|[^|\n]*\|\s*[\d.]+[eE][+\-]?\d+\s*\|',
    re.MULTILINE,
)

# Placement stage: estimated timing after detail_place
# report_metrics writes: "clock   period_min = <val>"
PLACE_ECP_PATTERN = re.compile(
    r'Report metrics stage 3.*?(?:core_)?cl[ock]*\s+period_min\s*=\s*([-\d.eE+]+)',
    re.DOTALL,
)

# CTS stage: total wirelength from CTS
CTS_WL_PATTERN = re.compile(r'Total wirelength:\s*([\d.eE+\-]+)')

# CTS-completion marker: the post-CTS report_metrics call ("Report metrics
# stage 4"). A run that fails *during* CTS never reaches this report, yet the
# combined log still holds the earlier global-placement HPWL table. We use this
# marker to decide whether the placement-HPWL fallback is legitimate: only a run
# that actually completed CTS may reuse the placement HPWL; a CTS-failed run must
# yield wl=None rather than the stale HPWL.
CTS_DONE_PATTERN = re.compile(r'Report metrics stage 4')

# CTS stage: timing after CTS
CTS_ECP_PATTERN = re.compile(
    r'Report metrics stage 4.*?(?:core_)?cl[ock]*\s+period_min\s*=\s*([-\d.eE+]+)',
    re.DOTALL,
)

# Final stage: detailed routing wirelength
DRT_WL_PATTERN = re.compile(
    r'\[INFO DRT-0198\]\s+Complete detail routing\.'
    r'.*?Total wire length\s*=\s*([\d.eE+\-]+)',
    re.DOTALL,
)

# Final stage: ECP from stage 6
FINAL_ECP_PATTERN = re.compile(
    r'Report metrics stage 6.*?(?:core_)?cl[ock]*\s+period_min\s*=\s*([-\d.eE+]+)',
    re.DOTALL,
)

# Worst slack patterns (fallback for ECP calculation)
WORST_SLACK_PATTERN = re.compile(
    r'worst slack\s*(?:max)?\s*=?\s*([-\d.eE+]+)',
    re.IGNORECASE,
)

# Clock period from SDC
CLK_PERIOD_PATTERN = re.compile(r'set\s+clk_period\s+([\d.eE+\-]+)')


def _finite_float(value) -> Optional[float]:
    """Convert a metric to float, rejecting booleans and non-finite values."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _first_float(pattern: re.Pattern, text: str) -> Optional[float]:
    """Return first match as float, or None."""
    m = pattern.search(text)
    if m:
        try:
            return _finite_float(m.group(1))
        except (ValueError, IndexError):
            pass
    return None


def _all_floats(pattern: re.Pattern, text: str) -> List[float]:
    """Return all matches as list of floats."""
    results = []
    for m in pattern.finditer(text):
        try:
            value = _finite_float(m.group(1))
            if value is not None:
                results.append(value)
        except (ValueError, IndexError):
            pass
    return results


def _extract_tns(content: str, stage: str) -> Optional[float]:
    """TNS for the stage. Prefer the CP_0-evaluated value written by eval_tns.sh
    ([TNS_EVAL][<stage>] tns_eval = X); fall back to the native stage TNS from
    report_tns (used for iter1 place/cts before CP_0 exists). TNS is <= 0."""
    m = re.search(rf'\[TNS_EVAL\]\[{stage}\]\s*tns_eval\s*=\s*([-\d.eE+]+)', content)
    if m:
        try:
            value = _finite_float(m.group(1))
            if value is not None:
                return value
        except ValueError:
            pass
    stage_num = {"place": 3, "cts": 4, "final": 6}.get(stage)
    if stage_num is not None:
        sect = re.search(rf'Report metrics stage {stage_num}\b.*?(?=Report metrics stage |\Z)',
                         content, re.DOTALL)
        if sect:
            t = re.search(r'\btns\s+(?:max\s+)?([-\d.eE+]+)', sect.group(0))
            if t:
                try:
                    value = _finite_float(t.group(1))
                    if value is not None:
                        return value
                except ValueError:
                    pass
    return None


def _extract_power(content: str, stage: str) -> Optional[float]:
    """Total power at CP_0 (W) written by eval_tns.sh: [POWER_EVAL][<stage>]
    power_eval = X. Only meaningful at the final stage (used for the power-budget
    constraint of objective=TNS_EVAL). None if absent."""
    m = re.search(rf'\[POWER_EVAL\]\[{stage}\]\s*power_eval\s*=\s*([-\d.eE+]+)', content)
    if m:
        try:
            return _finite_float(m.group(1))
        except ValueError:
            pass
    return None


def extract_placement_metrics(log_content: str) -> Dict[str, Optional[float]]:
    """Extract metrics after detail_place (stage 3)."""
    metrics = {"wl": None, "ecp": None}

    # Wirelength: use last HPWL value (from global placement, most recent)
    hpwl_values = _all_floats(HPWL_PATTERN, log_content)
    if hpwl_values:
        metrics["wl"] = hpwl_values[-1]

    # ECP: clock_period_min from stage 3 report
    ecp = _first_float(PLACE_ECP_PATTERN, log_content)
    if ecp is not None:
        metrics["ecp"] = ecp

    return metrics


def extract_cts_metrics(log_content: str) -> Dict[str, Optional[float]]:
    """Extract metrics after CTS (stage 4)."""
    metrics = {"wl": None, "ecp": None}

    # Wirelength: the "Total wirelength" line is produced by global routing,
    # which only runs in the route stage — it is NOT present at post-CTS DRP
    # time. So for a run that COMPLETED CTS we fall back to the placement HPWL:
    # CTS does not change signal-net HPWL, and at post-CTS time the combined log
    # still contains the global-placement convergence table (CTS adds no such
    # table of its own).
    #
    # Crucially, the fallback is gated on CTS actually having completed
    # (CTS_DONE_PATTERN). A run that fails during CTS still has the placement
    # HPWL table in its combined log; without this gate it would be assigned a
    # healthy-looking wl and could be ranked as a survivor/winner by DRP — i.e.
    # failed runs would beat successful ones. A CTS-failed run must yield None.
    cts_wl_values = _all_floats(CTS_WL_PATTERN, log_content)
    if cts_wl_values:
        metrics["wl"] = cts_wl_values[-1]
    elif CTS_DONE_PATTERN.search(log_content):
        hpwl_values = _all_floats(HPWL_PATTERN, log_content)
        if hpwl_values:
            metrics["wl"] = hpwl_values[-1]
    # else: CTS did not complete -> leave wl = None (do not trust stale HPWL).

    # ECP: clock_period_min from stage 4 report
    ecp = _first_float(CTS_ECP_PATTERN, log_content)
    if ecp is not None:
        metrics["ecp"] = ecp

    return metrics


def extract_final_metrics(log_content: str) -> Dict[str, Optional[float]]:
    """Extract metrics after routing (stage 5/6)."""
    metrics = {"wl": None, "ecp": None}

    # Wirelength: detailed routing total wire length
    wl = _first_float(DRT_WL_PATTERN, log_content)
    if wl is not None:
        metrics["wl"] = wl

    # ECP: clock_period_min from stage 6 report
    ecp = _first_float(FINAL_ECP_PATTERN, log_content)
    if ecp is not None:
        metrics["ecp"] = ecp

    return metrics


# ---------------------------------------------------------------------------
# Structured extraction from the flow's per-substep metric JSONs. These are far
# more robust than regex-scraping the combined log (the source of several silent
# extraction bugs). The flow emits one <step>.json per substep with stable keys
# like "<prefix>__timing__setup__tns"; ecp is derived from fmax (ecp_ps = 1e12/fmax).
# ---------------------------------------------------------------------------
_STAGE_JSON = {
    "place": {"json": "3_5_place_dp.json", "prefix": "detailedplace",
              "wl_key": "route__wirelength__estimated"},
    "cts":   {"json": "4_1_cts.json", "prefix": "cts",
              "wl_key": "route__wirelength__estimated"},
    # final: timing/power in 6_report.json (finish), routed wirelength in 5_2_route.json.
    "final": {"json": "6_report.json", "prefix": "finish",
              "wl_json": "5_2_route.json", "wl_prefix": "detailedroute",
              "wl_key": "route__wirelength"},
}


def _load_json(path: Path) -> Optional[dict]:
    """Load a substep JSON. A MISSING file is expected (returns None quietly); a
    malformed/unreadable file is a real problem and is surfaced to stderr."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as e:
        print(f"[extract][WARN] cannot parse {path}: {e}", file=sys.stderr)
        return None


def _num(d: Optional[dict], key: str) -> Optional[float]:
    if not d:
        return None
    return _finite_float(d.get(key))


def _extract_from_json(json_dir: Optional[Path], stage: str) -> Optional[Dict[str, Optional[float]]]:
    """Native stage metrics from the substep JSONs. None if the primary JSON is
    absent (caller then falls back to log regex)."""
    spec = _STAGE_JSON.get(stage)
    if spec is None or json_dir is None:
        return None
    d = _load_json(Path(json_dir) / spec["json"])
    if d is None:
        return None
    P = spec["prefix"]
    m: Dict[str, Optional[float]] = {"wl": None, "ecp": None, "tns": None, "power": None}
    fmax = _num(d, f"{P}__timing__fmax")
    if fmax and fmax > 0:
        m["ecp"] = 1.0e12 / fmax               # min clock period in ps
    m["tns"] = _num(d, f"{P}__timing__setup__tns")   # native (own-clock) setup TNS
    m["power"] = _num(d, f"{P}__power__total")
    wl_json = spec.get("wl_json", spec["json"])
    wl_pref = spec.get("wl_prefix", P)
    wd = d if wl_json == spec["json"] else _load_json(Path(json_dir) / wl_json)
    m["wl"] = _num(wd, f"{wl_pref}__{spec['wl_key']}")
    return m


def reference_ecp(log_path: Path, json_dir: Path, *, time_unit: str = "ps") -> Optional[float]:
    """Read the same baseline minimum clock period from old text or modern JSON.

    CP0's 0.9 factor and TT evaluation are applied by the existing controller.
    This helper only handles the physical report's representation and units.
    """
    content = log_path.read_text()
    match = FINAL_ECP_PATTERN.search(content)
    if match:
        return _finite_float(match.group(1))
    period = re.search(r'clock period to\s*([\d.]+)', content)
    slack = re.search(r'Report metrics stage 6, finish[\s\S]*?wns max\s+([-\d.]+)', content)
    if period and slack:
        return _finite_float(float(period.group(1)) - float(slack.group(1)))
    metrics = _extract_from_json(json_dir, "final")
    ecp_ps = metrics.get("ecp") if metrics else None
    if ecp_ps is None:
        return None
    if time_unit not in {"ps", "ns"}:
        raise ValueError("unsupported native clock unit: " + time_unit)
    return ecp_ps if time_unit == "ps" else ecp_ps / 1000


def extract_metrics(log_path: Path, stage: str,
                    json_dir: Optional[Path] = None) -> Dict[str, Optional[float]]:
    """
    Extract {wl, ecp, tns, power} for a run at the given stage.

    Prefers the flow's structured substep JSONs (json_dir); falls back to regex on
    the combined log when the JSON is missing (backward compatibility). The CP_0
    [TNS_EVAL]/[POWER_EVAL] tags that eval_tns.sh writes to the log always OVERRIDE
    the native tns/power (that is the objective for objective=TNS_EVAL).
    """
    try:
        content = log_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"[WARN] Failed to read {log_path}: {e}", file=sys.stderr)
        content = ""

    # Primary: structured JSON. Fallback: log regex.
    result = _extract_from_json(json_dir, stage)
    if result is None:
        extractor = {"place": extract_placement_metrics,
                     "cts": extract_cts_metrics,
                     "final": extract_final_metrics}.get(stage)
        if extractor is None:
            print(f"[ERROR] Unknown stage: {stage}", file=sys.stderr)
            return {"wl": None, "ecp": None, "tns": None, "power": None}
        result = extractor(content)
        result.setdefault("tns", _extract_tns(content, stage))
        result.setdefault("power", None)

    # CP_0 overrides from the log tags (unambiguous single lines eval_tns writes).
    # Record WHERE tns came from so downstream can require a real CP_0 eval when one is
    # expected (iter2+/final) and not silently rank a CP_0-eval TNS against a native
    # own-clock TNS: "cp0_eval" (the [TNS_EVAL] tag), "native" (own-clock stage TNS), or
    # "missing".
    tns_tag = None
    m = re.search(rf'\[TNS_EVAL\]\[{stage}\]\s*tns_eval\s*=\s*([-\d.eE+]+)', content)
    if m:
        try:
            tns_tag = float(m.group(1))
        except ValueError:
            pass
    if tns_tag is not None:
        result["tns"] = tns_tag
        result["tns_source"] = "cp0_eval"
    elif result.get("tns") is not None:
        result["tns_source"] = "native"
    else:
        result["tns_source"] = "missing"

    pwr = _extract_power(content, stage)   # tag-only helper
    if pwr is not None:
        result["power"] = pwr

    for k in ("wl", "ecp", "tns", "power"):
        result[k] = _finite_float(result.get(k))
    return result


def compute_combo(wl: Optional[float], ecp: Optional[float],
                  wl_base: float, ecp_base: float,
                  weight_wl: float = 0.5, weight_ecp: float = 0.5) -> Optional[float]:
    """Compute combo metric: weight_wl * (wl/wl_base) + weight_ecp * (ecp/ecp_base)."""
    values = tuple(_finite_float(value) for value in (
        wl, ecp, wl_base, ecp_base, weight_wl, weight_ecp))
    wl, ecp, wl_base, ecp_base, weight_wl, weight_ecp = values
    if any(value is None for value in values):
        return None
    if wl_base <= 0 or ecp_base <= 0:
        return None
    combo = weight_wl * (wl / wl_base) + weight_ecp * (ecp / ecp_base)
    return combo if math.isfinite(combo) else None


def extract_all_runs(log_dir: Path, platform: str, design: str,
                     num_runs: int, stage: str,
                     wl_base: float = 1.0, ecp_base: float = 1.0,
                     weight_wl: float = 0.5, weight_ecp: float = 0.5,
                     require_cp0_tns: bool = False) -> List[Dict]:
    """
    Extract metrics for all runs at a given stage.

    Looks for log files in: log_dir/{platform}/{design}/run_{i}/
    The main log file is the concatenation of all stage logs, or a single
    log file capturing the full make output.

    require_cp0_tns: once CP_0 is established (objective=TNS_EVAL, iter2+/final), a
    run whose TNS did NOT come from the CP_0 eval (tns_source != "cp0_eval") gets
    TNS_EVAL = None. Otherwise a partial eval_tns failure would let its own-clock
    native |TNS| (usually SMALLER — relaxed clock) be ranked against CP_0 values and
    wrongly beat them. The native tns/tns_source stay as diagnostics only.

    Returns:
        List of dicts with keys: run_id, wl, ecp, combo, tns, TNS_EVAL, tns_source,
        power, log_path.
    """
    results = []
    for run_id in range(1, num_runs + 1):
        run_log_dir = log_dir / platform / design / f"run_{run_id}"

        # Try to find the log file - look for the stage-specific or combined log
        log_file = None

        # First try: combined log from run_stage.sh redirect
        parent_log = log_dir / f"{platform}_{design}_run{run_id}.log"
        if parent_log.exists():
            log_file = parent_log

        # Second try: look in the run-specific log directory
        if log_file is None and run_log_dir.exists():
            # Find any .log file
            log_files = sorted(run_log_dir.glob("*.log"))
            if log_files:
                # Use the largest/most recent log
                log_file = max(log_files, key=lambda p: p.stat().st_size)

        if log_file is None:
            print(f"[WARN] No log file found for run {run_id}", file=sys.stderr)
            results.append({
                "run_id": run_id,
                "wl": None,
                "ecp": None,
                "combo": None,
                "tns": None,
                "TNS_EVAL": None,
                "tns_source": "missing",
                "power": None,
                "log_path": None,
            })
            continue

        # run_log_dir holds the flow's per-substep metric JSONs (primary source).
        metrics = extract_metrics(log_file, stage,
                                  json_dir=run_log_dir if run_log_dir.exists() else None)
        combo = compute_combo(
            metrics["wl"], metrics["ecp"],
            wl_base, ecp_base,
            weight_wl, weight_ecp,
        )
        tns = metrics.get("tns")
        tns_source = metrics.get("tns_source", "missing")
        # Objective value for objective=TNS_EVAL: |TNS| (minimize). With
        # require_cp0_tns, only a genuine CP_0 eval qualifies — a native own-clock
        # TNS is NOT comparable and must not enter the ranking (None -> treated as
        # a failed run: sorted last, prioritized victim).
        tns_eval = abs(tns) if tns is not None else None
        if require_cp0_tns and tns_source != "cp0_eval":
            if tns_eval is not None:
                print(f"[extract][WARN] run {run_id}: TNS is '{tns_source}' but CP_0 "
                      f"is established — TNS_EVAL nulled (native kept as diagnostic).",
                      file=sys.stderr)
            tns_eval = None
        results.append({
            "run_id": run_id,
            "wl": metrics["wl"],
            "ecp": metrics["ecp"],
            "combo": combo,
            "tns": tns,
            "TNS_EVAL": tns_eval,
            "tns_source": tns_source,   # cp0_eval | native | missing
            "power": metrics.get("power"),   # CP_0 total power (W), final-stage constraint
            "log_path": str(log_file),
        })

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Extract stage-aware metrics from OpenROAD flow logs."
    )
    parser.add_argument("--log-dir", type=Path, required=True,
                        help="Root log directory")
    parser.add_argument("--platform", required=True)
    parser.add_argument("--design", required=True)
    parser.add_argument("--num-runs", type=int, required=True)
    parser.add_argument("--stage", choices=["place", "cts", "final"], required=True)
    parser.add_argument("--wl-base", type=float, default=1.0)
    parser.add_argument("--ecp-base", type=float, default=1.0)
    parser.add_argument("--weight-wl", type=float, default=0.5)
    parser.add_argument("--weight-ecp", type=float, default=0.5)
    parser.add_argument("--require-cp0-tns", action="store_true",
                        help="TNS_EVAL counts only runs whose TNS came from the CP_0 "
                             "eval (tns_source==cp0_eval); native fallbacks get "
                             "TNS_EVAL=None. Set once CP_0 is established.")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output JSON file (default: stdout)")

    args = parser.parse_args()

    results = extract_all_runs(
        log_dir=args.log_dir,
        platform=args.platform,
        design=args.design,
        num_runs=args.num_runs,
        stage=args.stage,
        wl_base=args.wl_base,
        ecp_base=args.ecp_base,
        weight_wl=args.weight_wl,
        weight_ecp=args.weight_ecp,
        require_cp0_tns=args.require_cp0_tns,
    )

    # Metrics artifacts are strict JSON. A non-finite value must have been normalized
    # to None above; fail here rather than publish NaN/Infinity as a valid observation.
    output = json.dumps(results, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
        print(f"Metrics written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()

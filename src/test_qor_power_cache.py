"""Persistent ECO QoR must report power for the current parasitic state."""

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def native_block() -> str:
    tree = ast.parse((ROOT / "src/main_orch.py").read_text())
    return next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "NODE_NET_TCL_BLOCK"
            for target in node.targets
        )
    )


def tcl(program: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["tclsh"], input=program, capture_output=True, text=True, check=False
    )


def reports() -> str:
    # Tcl stubs exercise the real helper. Parasitic updates invalidate timing,
    # but retain cached power until activity invalidation, as in pinned STA.
    return """
set current_power 0.15
set cached_power {}
set refreshes 0
proc set_power_activity {args} {}
proc unset_power_activity {args} {
  set ::cached_power {}
  incr ::refreshes
}
proc tee {args} {
  set command [lindex $args end]
  set f [open [lindex $args 1] a]
  switch -- [lindex $command 0] {
    report_wns {puts $f {wns 0.000}}
    report_tns {puts $f {tns 0.000}}
    report_design_area {puts $f {Design area 123 u^2 40% utilization.}}
    report_power {
      if {$::cached_power eq {}} {set ::cached_power $::current_power}
      puts $f "Total 0.1 0.02 0.03 $::cached_power"
    }
  }
  close $f
}
"""


def test_actual_helper_refreshes_power_after_parasitic_change(tmp_path):
    first, second = tmp_path / "first.txt", tmp_path / "second.txt"
    result = tcl(
        reports()
        + native_block()
        + f"""
set ::env(TIMINGECO_EF_LEAF) 1
dump_iter_qor {{{first}}}
set current_power 0.16
dump_iter_qor {{{second}}}
puts "REFRESHES=$refreshes"
"""
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert "Total 0.1 0.02 0.03 0.15" in first.read_text()
    assert "Total 0.1 0.02 0.03 0.16" in second.read_text()
    assert "REFRESHES=2" in result.stdout
    # Original report sections and timing/area remain available to consumers.
    assert "=== WNS ===\nwns 0.000" in second.read_text()
    assert "=== TNS ===\ntns 0.000" in second.read_text()
    assert "=== AREA ===\nDesign area 123" in second.read_text()


def test_independent_native_mode_retains_its_activity_model(tmp_path):
    target = tmp_path / "native.txt"
    result = tcl(
        reports()
        + native_block()
        + f"""
unset -nocomplain ::env(TIMINGECO_EF_LEAF)
set cached_power 0.22
dump_iter_qor {{{target}}}
puts "REFRESHES=$refreshes"
"""
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert "Total 0.1 0.02 0.03 0.22" in target.read_text()
    assert "REFRESHES=0" in result.stdout


def test_refresh_failure_cannot_silently_publish_cached_power(tmp_path):
    target = tmp_path / "failed.txt"
    result = tcl(
        reports()
        + native_block()
        + f"""
set ::env(TIMINGECO_EF_LEAF) 1
proc unset_power_activity {{args}} {{error {{activity refresh failed}}}}
puts "FAILED=[catch {{dump_iter_qor {{{target}}}}} message]"
puts "MESSAGE=$message"
"""
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert "FAILED=1" in result.stdout
    assert "MESSAGE=activity refresh failed" in result.stdout
    assert "Total " not in target.read_text()


def test_timestamp_does_not_require_lazy_tcl_timezone_loading(tmp_path):
    target = tmp_path / "without-timezone.txt"
    result = tcl(
        reports()
        + native_block()
        + f"""
rename clock original_clock
proc clock {{command args}} {{
  if {{$command eq {{seconds}}}} {{return [original_clock seconds]}}
  error {{timezone formatting unavailable in embedded Tcl}}
}}
set ::env(TIMINGECO_EF_LEAF) 1
puts "FAILED=[catch {{dump_iter_qor {{{target}}}}} message]"
"""
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert "FAILED=0" in result.stdout
    assert "# iter_qor dump at epoch " in target.read_text()
    assert "Total 0.1 0.02 0.03 0.15" in target.read_text()

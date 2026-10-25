"""The expert's documented read-only probe must reach the native interpreter."""

import ast
import contextlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import LLM_call
from LLM_call import parse_commands, sanitize_tcl_output, validate_reply

ROOT = Path(__file__).resolve().parents[1]
NETWORK = """
namespace eval sta {}
proc get_nets {args} {
    if {[lindex $args end] eq "missing"} {return {}}
    return net_sta
}
proc sta::sta_to_db_net {net} {return dbnet}
proc dbnet {method} {
    switch $method {
        getITerms {return {driver sink}}
        getBTerms {return port}
        getName {return net_a}
    }
}
proc driver {method} {
    switch $method {getInst {return driver_inst} getMTerm {return driver_term}}
}
proc sink {method} {
    switch $method {getInst {return sink_inst} getMTerm {return sink_term}}
}
proc driver_inst {method} {
    switch $method {getName {return drv} getMaster {return driver_master}}
}
proc sink_inst {method} {
    switch $method {getName {return {sink[3]}} getMaster {return sink_master}}
}
proc driver_master {method} {return BUF}
proc sink_master {method} {return AND}
proc driver_term {method} {
    switch $method {getName {return Y} getIoType {return OUTPUT}}
}
proc sink_term {method} {
    switch $method {getName {return A} getIoType {return INPUT}}
}
proc port {method} {
    switch $method {getName {return {out[0]}} getIoType {return OUTPUT}}
}
proc write_verilog {args} {}
"""


def collector(root: Path) -> str:
    """Render the actual native collector, without its later routing sequence."""
    tree = ast.parse((ROOT / "src/main_orch.py").read_text())
    block = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.JoinedStr)
        and any(
            isinstance(item, ast.Constant)
            and isinstance(item.value, str)
            and "set _probe_cmds" in item.value
            for item in node.values
        )
    )
    values = {
        "i": 0,
        "PROBE_RESPONSES_FILE": str(root / "probes.txt"),
        "ECO_out": str(root / "commands.tcl"),
        "eco_error_log": str(root / "errors.txt"),
        "_route_seq": "",
        "verilog_out": str(root / "view.v"),
        "MARK": "DONE",
    }
    return eval(
        compile(ast.Expression(block), "native-probe-collector", "eval"), values
    )


def run_tcl(script: str) -> str:
    result = subprocess.run(
        ["tclsh"], input=script, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    return result.stdout


def prelude() -> str:
    return "source {" + str(ROOT / "OpenROAD_utils/eco_procs.tcl") + "}\n" + NETWORK


class NativeProbeTests(unittest.TestCase):
    def test_connectivity_probe_returns_the_rows_it_prints(self):
        text = run_tcl(
            prelude()
            + '\nset rows [eco_net_sink_report net_a]\nforeach row $rows {puts "RETURNED=$row"}\n'
        )
        for row in (
            "NET net_a terminals=3",
            "PIN drv/Y direction=OUTPUT master=BUF",
            "PIN sink[3]/A direction=INPUT master=AND",
            "PORT out[0] direction=OUTPUT",
        ):
            self.assertIn(row, text)
            self.assertIn("RETURNED=" + row, text)

    def test_actual_native_collector_delivers_complete_connectivity_to_next_prompt(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "commands.tcl").write_text("eco_net_sink_report net_a\n")
            run_tcl(prelude() + "\n" + collector(root))
            text = (root / "probes.txt").read_text()
            self.assertIn("NET net_a terminals=3", text)
            self.assertIn("PIN sink[3]/A direction=INPUT master=AND", text)
            self.assertIn("PORT out[0] direction=OUTPUT", text)
            self.assertNotIn("(no rows returned)", text)
            with contextlib.ExitStack() as stack:
                for name, value in vars(LLM_call).items():
                    if isinstance(value, Path):
                        stack.enter_context(patch.object(LLM_call, name, root / name))
                LLM_call.PROBE_RESPONSES_FILE.write_text(text)
                _system, prompt = LLM_call.build_prompt("original expert guide", [])
            self.assertIn("<probe_responses>", prompt)
            self.assertIn(text.strip(), prompt)

    def test_pair_queries_and_native_errors_are_still_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "commands.tcl").write_text(
                "eco_net_sink_report missing\neco_top_paths_through inst drv\n"
            )
            run_tcl(
                prelude()
                + "\nproc eco_top_paths_through {args} {return {{endpoint -3.5} {second 0.0}}}\n"
                + collector(root)
            )
            text = (root / "probes.txt").read_text()
            self.assertIn(
                "ERROR: eco_net_sink_report: expected one net 'missing'", text
            )
            self.assertTrue(
                any(line.split() == ["endpoint", "-3.5"] for line in text.splitlines())
            )
            self.assertTrue(
                any(line.split() == ["second", "0.0"] for line in text.splitlines())
            )
            self.assertIn(
                "1 command(s) succeeded, 1 failed", (root / "errors.txt").read_text()
            )

    def test_network_probe_survives_transport_and_original_validation(self):
        command = "eco_net_sink_report [get_name [get_nets -of_objects [get_pins {_534_/CON}]]]"
        reply = sanitize_tcl_output("### Tcl recipe\n```tcl\n" + command + "\n```")
        self.assertEqual(parse_commands(reply), [command])
        self.assertEqual(validate_reply(reply, [], set()), (True, ""))


if __name__ == "__main__":
    unittest.main()

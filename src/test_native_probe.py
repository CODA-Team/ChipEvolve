"""The expert's documented read-only probe must reach the native interpreter."""

import ast
import contextlib
import json
import subprocess
import tempfile
import types
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


def native_function(name: str, namespace: dict):
    """Load one native function without starting the loop or plotting imports."""
    tree = ast.parse((ROOT / "src/main_orch.py").read_text())
    node = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name
    )
    compiled = compile(
        ast.Module(body=[node], type_ignores=[]), "native-context", "exec"
    )
    code = next(
        value for value in compiled.co_consts if isinstance(value, types.CodeType)
    )
    defaults = tuple(ast.literal_eval(value) for value in node.args.defaults)
    return types.FunctionType(code, namespace, name, defaults)


class TimingContextTests(unittest.TestCase):
    def fixture(self, root: Path) -> Path:
        path = root / "context.json"
        path.write_text(
            json.dumps(
                {
                    "tns_ps": -17813.3,
                    "num_violating_endpoints": 50,
                    "paths": [{"endpoint": "axi_req_o[113]", "slack_ps": -366.35}],
                }
            )
        )
        path.with_suffix(".toon").write_text(
            "tns_ps: -17813.3\nnum_violating_endpoints: 50\n\npath[1]{endpoint,slack_ps}:\naxi_req_o[113],-366.35\n"
        )
        return path

    def binder(self):
        return native_function("bind_timing_context", {"json": json, "Path": Path})

    def test_native_total_is_distinct_from_subset_and_preserves_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.fixture(Path(directory))
            before = json.loads(path.read_text())
            body = path.with_suffix(".toon").read_text().split("\n\n", 1)[1]
            self.binder()(path, -493796.406)
            value = json.loads(path.read_text())
            self.assertEqual(value["tns_ps"], -493796.406)
            self.assertEqual(value["tns_scope"], "design")
            self.assertEqual(value["reported_paths_tns_ps"], -17813.3)
            self.assertEqual(value["num_violating_endpoints"], 50)
            self.assertEqual(value["num_violating_endpoints_scope"], "reported_paths")
            self.assertEqual(value["paths"], before["paths"])
            toon = path.with_suffix(".toon").read_text()
            self.assertIn("tns_ps: -493796.406\n", toon)
            self.assertIn("reported_paths_tns_ps: -17813.3\n", toon)
            self.assertEqual(toon.split("\n\n", 1)[1], body)

    def test_retry_preserves_original_reported_subset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.fixture(Path(directory))
            binder = self.binder()
            binder(path, -493796.406)
            first = path.with_suffix(".toon").read_text()
            binder(path, -493796.406)
            self.assertEqual(path.with_suffix(".toon").read_text(), first)
            self.assertEqual(
                json.loads(path.read_text())["reported_paths_tns_ps"], -17813.3
            )

    def test_missing_native_total_keeps_subset_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.fixture(Path(directory))
            self.binder()(path, None)
            value = json.loads(path.read_text())
            self.assertIsNone(value["tns_ps"])
            self.assertEqual(value["tns_scope"], "unavailable")
            self.assertEqual(value["reported_paths_tns_ps"], -17813.3)
            self.assertIn("tns_ps: \n", path.with_suffix(".toon").read_text())

    def test_actual_model_hook_binds_current_tool_total_first(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.fixture(Path(directory))
            seen = []

            def transport(*args, **kwargs):
                seen.append(json.loads(path.read_text())["tns_ps"])
                return types.SimpleNamespace(returncode=0)

            namespace = {
                "Path": Path,
                "DYNAMIC_CONTEXT_JSON": str(path),
                "WNS_TNS_FILE": str(Path(directory) / "wns_tns.txt"),
                "parse_wns_tns_file": lambda _: {"wns": -366.345, "tns": -493796.406},
                "bind_timing_context": self.binder(),
                "subprocess": types.SimpleNamespace(
                    run=transport, TimeoutExpired=subprocess.TimeoutExpired
                ),
                "sys": types.SimpleNamespace(executable="unused"),
                "LLM_CALL": "unused",
            }
            call = native_function("run_llm", namespace)
            self.assertEqual(call(), (True, "ok"))
            self.assertEqual(seen, [-493796.406])

    def test_live_summary_refresh_is_ordered_before_each_model_call(self):
        events = []
        namespace = {
            "WNS_TNS_FILE": "/tmp/current-summary.txt",
            "PARA": "TIMING_DONE",
            "send": lambda proc, command: events.append(("send", command)),
            "wait_for_sentinel": lambda proc: events.append(("wait", proc)),
        }
        refresh = native_function("refresh_model_timing", namespace)
        refresh("same-managed-session")
        self.assertEqual([event[0] for event in events], ["send", "wait"])
        self.assertIn('open "/tmp/current-summary.txt" w', events[0][1])
        self.assertIn("report_wns -digits 3", events[0][1])
        self.assertIn("report_tns -digits 3", events[0][1])
        self.assertIn("puts TIMING_DONE", events[0][1])
        tree = ast.parse((ROOT / "src/main_orch.py").read_text())
        loop = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "run_loop"
        )
        calls = {
            n.func.id: n.lineno
            for n in ast.walk(loop)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in {"refresh_model_timing", "run_llm"}
        }
        self.assertLess(calls["refresh_model_timing"], calls["run_llm"])

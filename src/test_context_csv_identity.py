"""Native CSV facts retain the names used by nodes and STA path stages."""

import ast
import subprocess
from pathlib import Path

from context_builder import ContextBuilderV5, Stage
from parsers.library_extractor import CellInfo, LibraryExtractor

ROOT = Path(__file__).resolve().parents[1]
NETWORK = r"""
namespace eval odb {}
proc odb::get_block {} {return block}
proc block {method args} {
    switch -- $method {
        getInsts {return {special ordinary load}}
        getNets {return {special_net ordinary_net}}
        getBTerms {return {}}
        dbuToMicrons {return [expr {[lindex $args 0]/1000.0}]}
    }
}
proc special {method} {
    switch -- $method {getName {return {unit/reg\[3\]$_DFF_}} getLocation {return {1000 2000}} getMaster {return master}}
}
proc ordinary {method} {
    switch -- $method {getName {return unit/reg3_DFF_} getLocation {return {3000 2000}} getMaster {return master}}
}
proc load {method} {
    switch -- $method {getName {return {unit/load\[2\]$_DFF_}} getLocation {return {11000 22000}} getMaster {return master}}
}
proc master {method} {
    switch -- $method {getName {return fixture_master} isBlock {return 0}}
}
proc special_net {method} {
    switch -- $method {getName {return {bus\[3\]$wire}} getSigType {return SIGNAL} getITerms {return {special_out load_a}} getBTerms {return {}} getWire {return NULL}}
}
proc ordinary_net {method} {
    switch -- $method {getName {return bus3wire} getSigType {return SIGNAL} getITerms {return {ordinary_out load_b}} getBTerms {return {}} getWire {return NULL}}
}
proc special_out {method} {
    switch -- $method {getInst {return special} getMTerm {return output_pin}}
}
proc ordinary_out {method} {
    switch -- $method {getInst {return ordinary} getMTerm {return output_pin}}
}
proc load_a {method} {
    switch -- $method {getInst {return load} getMTerm {return input_a}}
}
proc load_b {method} {
    switch -- $method {getInst {return load} getMTerm {return input_b}}
}
proc output_pin {method} {
    switch -- $method {getName {return Q} getIoType {return OUTPUT}}
}
proc input_a {method} {
    switch -- $method {getName {return A} getIoType {return INPUT}}
}
proc input_b {method} {
    switch -- $method {getName {return B} getIoType {return INPUT}}
}
"""


def exported_builder(tmp_path: Path) -> ContextBuilderV5:
    tree = ast.parse((ROOT / "src/main_orch.py").read_text())
    block = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "NODE_NET_TCL_BLOCK"
            for target in node.targets
        )
    )
    nodes, nets = tmp_path / "nodes.csv", tmp_path / "nets.csv"
    result = subprocess.run(
        ["tclsh"],
        input=NETWORK + block + f"\nwrite_node_and_net_files {{{nodes}}} {{{nets}}}\n",
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    return ContextBuilderV5(None, node_file=nodes, net_file=nets)


def test_exported_driver_names_join_exact_nodes_without_lossy_alias(tmp_path):
    builder = exported_builder(tmp_path)
    assert builder.inst_to_nets["unit/reg[3]$_DFF_"] == ["bus[3]$wire"]
    assert "unit/reg[3]$_DFF_" in builder.node_meta
    assert builder.inst_pin_to_net[("unit/reg[3]$_DFF_", "Q")] == "bus[3]$wire"


def test_preserved_net_names_do_not_collide_with_ordinary_names(tmp_path):
    builder = exported_builder(tmp_path)
    assert set(builder.net_fanout) == {"bus[3]$wire", "bus3wire"}
    assert builder.inst_to_nets["unit/reg3_DFF_"] == ["bus3wire"]


def test_exported_special_sink_names_find_their_cell_master(tmp_path):
    builder = exported_builder(tmp_path)
    sink = builder.net_sinks["bus3wire"][0]
    assert sink == "unit/load[2]$_DFF_/B"
    assert builder.node_meta[sink.rsplit("/", 1)[0]]["master"] == "fixture_master"


def test_actual_context_reader_recovers_wire_length_and_sink_capacitance(tmp_path):
    builder = exported_builder(tmp_path)
    library = LibraryExtractor.__new__(LibraryExtractor)
    library.cells = {
        "fixture_master": CellInfo(
            name="fixture_master",
            type="fixture",
            drive_strength="x1",
            vt_flavor="R",
            tech_base="ASAP7_75t",
            area=1.0,
            input_caps_ff={"A": 2.0, "B": 1.0},
        )
    }
    builder.library = library
    stage = Stage(
        stage=0,
        driver_pin="unit/reg[3]$_DFF_/Q",
        cell="fixture_master",
        inst="unit/reg[3]$_DFF_",
        load_cap_ff=10.0,
    )
    wire_cap, wire_length = builder._wire_decomp(stage)
    assert wire_cap == 8.0 and wire_length == 30.0

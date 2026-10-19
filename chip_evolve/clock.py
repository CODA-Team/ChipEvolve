"""Bind an existing unit-explicit SDC to the native Flow clock variable."""

import re


def _native_clock_template(serialized: str, clock: float) -> bool:
    """Recognize the native tuner's single-clock variable template."""
    periods = re.findall(r"(?m)^set clk_period ([\d.eE+-]+)[ \t]*$", serialized)
    ports = re.findall(
        r"(?m)^set clk_port_name ([A-Za-z_][A-Za-z0-9_./:-]*)[ \t]*$", serialized
    )
    clocks = re.findall(r"(?m)^create_clock[^\n]*$", serialized)
    port_bindings = re.findall(
        r"(?m)^set clk_port \[get_ports \$clk_port_name\][ \t]*$", serialized
    )
    return (
        serialized.startswith("set_cmd_units -time ps\n")
        and len(periods) == len(ports) == len(clocks) == len(port_bindings) == 1
        and abs(float(periods[0]) - clock) <= 1e-6
        and re.search(r"-period\s+\$clk_period\s", clocks[0]) is not None
        and re.search(r"\s\$clk_port[ \t]*$", clocks[0]) is not None
    )


def flow_sdc(serialized: str, clock_ns: float) -> str:
    clock = clock_ns * 1000
    pattern = r"(create_clock[^\n]*?-period\s+)([\d.eE+-]+)"
    matches = re.findall(pattern, serialized)
    if not matches and _native_clock_template(serialized, clock):
        # Keep variable-based I/O constraints live when the native tuner edits
        # clk_period. Serializing them here would freeze their expressions.
        return serialized
    if not matches or any(abs(float(match[1]) - clock) > 1e-6 for match in matches):
        raise ValueError(
            "Flow requires one declared period, including matching virtual clocks"
        )
    if not serialized.startswith("set_cmd_units -time ps\n"):
        raise ValueError("Flow needs OpenSTA's explicit ps serialization")
    ports = re.findall(r"create_clock[^\n]*?\[get_ports\s+\{?([^\s}\]]+)", serialized)
    if len(ports) != 1:
        raise ValueError("Native CP0 Flow needs one physical clock port")
    return (
        "set clk_period "
        + str(clock)
        + "\n"
        + "set clk_port_name "
        + ports[0]
        + "\n"
        + re.sub(pattern, r"\1$clk_period", serialized)
    )

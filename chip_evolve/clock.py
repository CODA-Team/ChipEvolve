"""Bind an existing unit-explicit SDC to the native Flow clock variable."""

import re


def flow_sdc(serialized: str, clock_ns: float, *, time_unit: str = "ps") -> str:
    if time_unit not in {"ps", "ns"}:
        raise ValueError("Unsupported native Flow time unit: " + time_unit)
    clock = clock_ns * (1000 if time_unit == "ps" else 1)
    pattern = r"(create_clock[^\n]*?-period\s+)([\d.eE+-]+)"
    matches = re.findall(pattern, serialized)
    if not matches or any(abs(float(match[1]) - clock) > 1e-6 for match in matches):
        raise ValueError(
            "Flow requires one declared period, including matching virtual clocks"
        )
    if not serialized.startswith("set_cmd_units -time " + time_unit + "\n"):
        raise ValueError("Flow needs explicit native " + time_unit + " serialization")
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

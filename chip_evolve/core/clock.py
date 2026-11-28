"""Bind an existing unit-explicit SDC to the native Flow clock variable."""

import re


def native_time_unit(serialized: str) -> str | None:
    """Read the explicit first command, allowing preceding comments/blank lines."""
    first = next(
        (
            line.strip()
            for line in serialized.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ),
        "",
    )
    match = re.fullmatch(r"set_cmd_units\s+-time\s+(ps|ns)", first)
    return match[1] if match else None


def _native_clock_template(serialized: str, clock: float, time_unit: str) -> bool:
    """Recognize the existing CP0 template, including matching virtual clocks."""
    periods = re.findall(r"(?m)^set clk_period ([\d.eE+-]+)[ \t]*$", serialized)
    ports = re.findall(
        r"(?m)^set clk_port_name ([A-Za-z_][A-Za-z0-9_./:-]*)[ \t]*$", serialized
    )
    clocks = re.findall(r"(?m)^create_clock[^\n]*$", serialized)
    bindings = re.findall(
        r"(?m)^set clk_port \[get_ports \$clk_port_name\][ \t]*$", serialized
    )
    return (
        native_time_unit(serialized) == time_unit
        and len(periods) == len(ports) == len(bindings) == 1
        and abs(float(periods[0]) - clock) <= 1e-6
        and bool(clocks)
        and sum(bool(re.search(r"\s\$clk_port[ \t]*$", line)) for line in clocks) == 1
        and all(
            re.search(r"-period\s+\$clk_period(?:\s|$)", line)
            and (
                line.rstrip().endswith("$clk_port")
                or line.rstrip().endswith("$clk_period")
            )
            for line in clocks
        )
    )


def flow_sdc(serialized: str, clock_ns: float, *, time_unit: str = "ps") -> str:
    if time_unit not in {"ps", "ns"}:
        raise ValueError("Unsupported native Flow time unit: " + time_unit)
    clock = clock_ns * (1000 if time_unit == "ps" else 1)
    pattern = r"(create_clock[^\n]*?-period\s+)([\d.eE+-]+)"
    matches = re.findall(pattern, serialized)
    if not matches and _native_clock_template(serialized, clock, time_unit):
        # Preserve native expressions when the tuner edits clk_period.
        return serialized
    if not matches or any(abs(float(match[1]) - clock) > 1e-6 for match in matches):
        raise ValueError(
            "Flow requires one declared period, including matching virtual clocks"
        )
    if native_time_unit(serialized) != time_unit:
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

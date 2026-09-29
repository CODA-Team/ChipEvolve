# OpenROAD/ORFS design-data capability

This plugin is the replaceable boundary for native design facts. The execution
foundation owns the run and raw artifacts; this process invokes the installed
OpenROAD/ORFS capability and emits the portable `query-data` snapshot consumed
by Data Foundation.

The supported adapters have deliberately separate business responsibilities:

- `opendb` reads an ODB with OpenROAD's native Tcl/OpenDB API. It emits
  instances, pins (including top-level ports), nets, explicit connectivity,
  placement boxes, pin geometry, routed segments, and vias. Pin geometry keeps
  its coordinate space (`master` for library pin shapes and `block` for ports);
  via records retain bottom/top layers and are never represented as a single
  rectangle.
- `opensta` invokes OpenROAD's built-in OpenSTA and the official
  `report_checks -format json` report. It preserves the original timing JSON,
  then emits indexed timing paths and ordered points with SI units. Each STA
  pin and top-level port is converted through OpenROAD's native
  `sta_to_db_pin` / `sta_to_db_port` bridge, so points carry the corresponding
  OpenDB pin, instance, and net identities. A point that the installed
  OpenROAD build cannot convert remains explicitly `unmapped`; the adapter
  never guesses a relationship from a name.
- `orfs` reads ORFS `metadata.json` directly. It does not scrape metrics from
  logs that already have a structured source.
- `report` runs one supported OpenROAD report mode (`timing`, `area`, or
  `power`) in an isolated analysis run. It generates the Tcl script
  from the selected staged inputs, keeps the original report and tool receipt,
  and rejects an invocation that exits successfully without creating the
  requested report. Timing and power JSON, plus the documented area summary,
  get structured results with locations back to the raw report. It does not
  accept an arbitrary command string.
- `command` remains the generic boundary for a deployment-owned extractor
  that implements the same snapshot contract.

For one unified snapshot, run the OpenDB and OpenSTA adapters in the same
execution workspace with the same `snapshot_id`, `run_id`, and output directory.
The timing adapter preserves the existing OpenDB JSONL files and adds timing
records; the resulting archive can be imported once. The native dbNetwork
conversion is performed by OpenROAD itself, not by Query-Agent or Data
Foundation. The mapping receipt is kept next to the timing records so a
single point can be marked `unmapped` without making an unsupported claim for
the whole snapshot.

Parser records cite raw sources by registered artifact identity when one is
known. During extraction, when the execution platform has not yet assigned an
artifact identity, they carry the source role and logical path (for example,
`raw_timing_report` plus `query-data/timing_report.json`). Data Foundation
resolves that reference against the run's registered artifact catalogue during
handoff; it does not match arbitrary host filenames.

Every invocation records the command, environment result, extractor log,
receipt, and `query-data.zip`. When the corresponding staged inputs are
present, ODB, LEF/DEF, netlist, Liberty, SDC, SPEF, timing-report, and ORFS
metadata files are also declared as raw artifacts with their input role. The
execution foundation hashes and stores those files; the data snapshot only
keeps their stable references. Failed extraction keeps its log and receipt and
is not reported as a successful snapshot. The plugin does not vendor a native
toolchain, so a pinned OpenROAD/ORFS installation can be replaced without
changing the execution kernel, Data Foundation, or Query-Agent.

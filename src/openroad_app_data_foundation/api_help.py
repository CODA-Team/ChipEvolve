"""Public API usage, retrieved by topic instead of copied into every model turn."""
TOPICS = {'run': 'Run identity, stage/source availability, metrics, library units and analysis setup.',
 'objects': 'Instance/pin/net discovery, statistics, connectivity and complete names.',
 'timing': 'Timing paths, extrema, engineering joins, constraints, comparisons and fresh path queries.',
 'physical': 'Placement, wire/via geometry, parasitics and violations.',
 'sources': 'Original files, source search/excerpts, evidence fragments and metric/batch reading.',
 'native': 'Real native OpenROAD queries, alternate-stage inputs and waiting for actual results.'}

GUIDES = {
    'run': '''Use the EDA data HTTP tool. GET responses usually carry their result in data.
Current snapshot: {snapshot_id}. Discover actual stages/IDs with GET /snapshots?design_id={design}.
Original states without an indexed snapshot are accessed through files or native-queries with odb_file.
S/run-inventory returns original stages, ODB digests, actual metric filenames/key coverage and indexed snapshot names.
Add ?stage=<actual stage> for compact discovery. metric_reports lists EVERY original JSON report in that stage,
including substage files with quantities absent from its representative report.
Metric selection defaults to one complete metric_reports collection without duplicating the representative report/database catalog;
detail=full or fields retrieves the catalog too. Every returned metric source/value/unit/analysis command is retained. Read the needed original with files/excerpt
or files/search, preserving its substage/source identity. Avoid full snapshot summaries or STA initialization for a quantity
already recorded in an original metric file. Never silently substitute an earlier iteration for a requested final-stage value.
Add metrics=<exact raw key or consecutive namespace components, comma separated> to return literal matching values from each
original report. Components such as hold, instance or setup__ws match entire component sequences, including keys carrying
a corner suffix. ALL matching corners remain separately labeled. Selected reports include literal unit_declarations.
When only part of a metric name is known, metric_name_contains=<comma-separated substrings>
selects matching original keys case-insensitively, with values/units/source and all literal corners.
Combine with stage and fields to avoid reading whole JSON files. It ORs with exact metrics selectors.
For example metrics=instance__area retrieves recorded cell area;
each substage stays separately identified, including an empty match in a report that does not declare that quantity.
Use it to distinguish original availability from index coverage; no indexed snapshot does not mean no original file.
indexed_snapshots identifies original stage indexes. Additional timing-query snapshots have a separate count and catalog route;
they are not silently relabeled original flow outputs, and remain accessible in the full snapshot catalog.
S/source-metadata returns literal config variables with continued lines joined, the actually loaded library units/nominal values,
SPEF headers and deduplicated per-stage flow timing/wall time, each with its original source.
Discover metric snapshot IDs from the snapshot catalog; do not construct IDs from a naming convention.
Canonical metrics preserve both unqualified source aggregates and EVERY literal raw-key corner separately;
corner_basis identifies literal labels versus observation context. Add corner=<literal> to select one declared corner.
GET /snapshots?design_id={design} discovers original snapshots and other runs with compact identities by default.
Use detail=full for complete catalog records; /snapshots/<snapshot_id>?detail=full restores any individual source manifest.
Add origin=flow for original stage indexes, origin=query for supplemental timing snapshots; default all retains both.
This uses actual parent metadata/query identity, so earlier query outputs do not inflate stage discovery.
S/run-inventory also accepts fields=<dotted paths through stages/report arrays> for compact selections,
preserving source/evidence and full-details recovery.
Let S=/snapshots/<snapshot_id>. URL-encode object names/IDs and query values.
S/summary gives compact run_summary, including DBU, die/core, counts and metric metadata.
S, S/summary and S/timing-context accept fields=<comma-separated dotted metadata paths> or detail=full.
For DBU use S/summary?fields=run_summary.dbu_per_micron; for original inputs use
S?fields=snapshot.source_artifacts,snapshot.run_summary.timing_context.producer.
Default metadata omits repeated full manifests; delivery.full_details retrieves everything. Use exact fields when possible.

S/source-metadata includes toolchain_receipt, timing_context, original_inputs, original_metric_scenarios and units.
S/analysis-setup reads actual native report_units, get_scenes, get_analysis_corners and loaded Liberty names,
using this snapshot's original timing inputs. native_ui_units are the tool's display units, distinct from interface s/F.
Actual scene names, explicitly defined analysis corners, command corner and configured snapshot labels stay separate;
an empty explicit corner list does not mean there is no default scene. Fresh query status and original source remain visible.
run_origin joins original flow identity, snapshot stage/top module, loaded ODB's original paths/digests and the literal
native manifest receipt design/platform/variant/run identity. It distinguishes flow runs from later extraction runs.
self_reported_tool_versions contains actual version banners in the original flow log, with original line positions/source.
Use fields=run_origin,configuration,libraries for design/config/loaded-library identity;
fields=toolchain_receipt,self_reported_tool_versions for tool binary identity and reported versions.
units separates interface SI/dbu values from literal original stage UI declarations, with sources.
original_metric_scenarios reads literal corner names from original metric keys, separately from the declared snapshot corner label.
Use fields=configuration,libraries,spef,timing_context (or other comma-separated top-level fields) for only needed sections.
Metadata detail=full retains all original sections. Receipt self-reported version "unknown" stays unknown.
S/artifacts/files supports kind=receipts, name_contains=<filename>, limit/offset. Use its real filters, not path=receipts.
''',
    'objects': '''S/instances?name=... or S/nets?name=... looks up native names.
S/instances|nets|pins/<native name or id>/provenance returns the native identity/locator,
exact source digests and declared original paths, plus literal original flow/toolchain identity in one read.
extraction_identity exposes each actual extraction run/attempt/source_type/declared_tool; native_locators
join by-name object keys and numeric locators to the exact ODB digest/path. No private parser ID/version is invented.
Its recovery routes use the actual record type entities (not objects or instances).
S/nets/<native name or id>/engineering?limit=N&offset=N returns complete driver/load counts and state,
sorted native driver_pins/load_pins with separate page metadata, net identity/type and original database evidence.
Choose limit large enough when the task requires all names; counts are independent of the returned page.
Add traverse=1&limit=<page size> to walk EVERY actual page internally from offset zero.
load_traversal/driver_traversal include full pin_names, actual page ranges, first/last pages,
returned/unique counts, missing/duplicate counts and verified name order. No count is inferred from a page.
internal_instance_count counts distinct pin parents across all pages, excluding ports.
For all loads and their instance count select fields=load_traversal.pin_names,load_traversal.internal_instance_count.
fields=<dotted fields> projects this net engineering result; omitted details remain retrievable.
include_instances=1 joins distinct driver_instances/load_instances with sorted native names and complete counts,
excluding ports and counting a shared pin parent once. instance_is_macro=0|1 filters these instance lists only;
pin counts still describe every native driver/load. instance_limit/instance_offset page the complete instance domain;
instance_order=asc|desc controls native-name order independently of pin pages. Select fields=load_count,driver_pins,load_instances
for load/driver facts and receiving instances together. Full names remain continuously readable with next_offset.
Add include_physical=1 to include_instances=1 to get each role's geometry and groups (is_macro=0|1|null)
in the SAME net read. geometry.bbox_union_um/status cover ALL matching distinct instances, regardless of pin/name paging.
The existing grouped object-statistics calculation supplies full counts/geometry; instance_is_macro filters both.
S/instances/<native name or id>/engineering returns master/type, placed location, bbox, both ODB/DEF orientation names,
and complete pin counts grouped by connected-net type in one call. Unconnected pins are explicitly unclassified.
S/instances/<name or id>/pair?with_instance=<other name or id> compares two arbitrary instances in this state.
left/right retain native names, bboxes and orientation; geometry.bbox_center_manhattan_um is their bbox-center distance.
shared_nets contains the complete distinct shared-net count and ordered items (name,native_name,object_id,signal_type).
signal_type=SIGNAL filters the NET's own type, not its pins' types. Omit it for every native net type.
limit/offset page after complete intersection/counting; order=asc|desc sorts unescaped native names bytewise.
Use fields=geometry,shared_nets for compact facts. Missing bboxes give null distance while connectivity stays readable.
Shared direct nets do not imply a timed path. All original pins/lists remain separately accessible.
These fields are under instance: use fields=instance.name,instance.bbox_um,instance.distinct_signal_net_count.
native_pin_classification contains complete indexed native pin counts, connected counts and distinct connected nets
grouped by the pin's OWN native type. Use fields=instance.bbox_um,instance.orientation,native_pin_classification
for geometry and native SIGNAL pin connections together. Check native_pin_classification_coverage:
partial identifies missing original classification; pin-inventory can obtain it from the actual native database.
S/instances/<name or id>/pin-inventory runs a native query for the pin's OWN dbMTerm classification,
separately from connected dbNet classification. connected_pin_counts_by_native_type and distinct_net_counts_by_native_pin_type
cover connected pins by their native pin type; pin_counts_by_native_type also includes unconnected pins.
pin_type=SIGNAL|CLOCK|POWER|GROUND and direction filter the complete pin list; limit/offset page it.
Add net_sort=load_count to obtain complete distinct-net rankings for those filtered pins,
with load_count and distinct receiving_macro_count. net_ranking orders by load count descending
then unescaped native name ascending; limit/offset page nets after the complete ranking.
The original native_name is retained alongside the unescaped name. Counts include all native loads.
Use this when the question refers to native SIGNAL pins: a CLOCK pin can temporarily connect to a SIGNAL-classified net.
instance.distinct_signal_net_count in engineering counts SIGNAL NET IDs; for native SIGNAL PIN connections read
pin-inventory's distinct_net_counts_by_native_pin_type.SIGNAL. Shared connections count once in either scope.
S/net-inventory returns all native SigType counts and special_net_count from the actual dbNet.isSpecial flag
in one native read of this original snapshot; do not substitute POWER+GROUND for this separate flag.
S/objects supports kind=instance|net|pin, name (exact), name_contains, name_prefix, ids=<comma-separated up to100 IDs>, parent_id, master, is_macro=0|1,
Object boolean filters/joins accept 0/1 or false/true; invalid values are explicit errors.
For pins, parent_instance=<native instance name> directly resolves the instance and returns its filtered pins;
no separate object-ID lookup is needed. Use signal_type=SIGNAL&fields=name,attributes.direction,attributes.net_name.
signal_type=SIGNAL|CLOCK|POWER|GROUND, port=0|1, driver_count/min/max, port_driven=0|1,
connected_to=<net name or id>&net_role=driver|load; sort=name|fanout|bbox_area&order=asc|desc;
For kind=instance, connected_to/net_role returns distinct owning instances of matching pins; ports are excluded.
Combine with is_macro=1 or statistics to count receiving macros; multiple pins on one instance count it once.
region=xmin,ymin,xmax,ymax with region_units=dbu|um (default dbu) and intersection=positive_area|touching.
Pin attributes include pin_name (local), native_name (full), net_name/net_id and signal_type of the connected native net; CLOCK is excluded from SIGNAL.
Use fields=object_id,name,attributes.pin_name,attributes.direction,attributes.net_name,attributes.signal_type for compact pins;
fields=object_id,name,attributes.master,attributes.fanout is compact for instances/nets. Omit fields to get full facts including geometry; limit/offset and next_offset page complete lists.
Add include_physical=1 to join placed geometry for every object on the page. For an entire macro inventory use
kind=instance&is_macro=1&sort=name&limit=200&include_physical=1&fields=name,attributes.master,attributes.orientation,physical.bbox_um.
Physical bbox_um is a named x_min/y_min/x_max/y_max box. This avoids per-object geometry operations and repeated evidence.
For long inventories add format=columns with explicit fields. object_columns declares the exact field order,
object_rows contains ordered arrays of their original values; page counts, sort order and recovery are unchanged.
This avoids repeating field names for every row and reduces list output size without losing facts.
physical.bbox_um_array supplies the same bbox as [x_min,y_min,x_max,y_max] in um,
so long geometry tables can carry the four coordinates directly, without repeated named-box keys or model conversion.
For largest macro use S/objects?kind=instance&is_macro=1&sort=bbox_area&order=desc&limit=1; ties use name descending.
ranking reports the full candidate count, leading integer dbu^2 area, tie count/rule and missing geometry count,
independent of pagination. Use compact fields=object_id,name plus a dependent batch to retrieve selected engineering facts.
Alternatively include_engineering=1 joins selected instance facts directly to the ranked page;
engineering.native_pin_classification includes the pin's OWN native counts and coverage in the SAME read,
so ranking an unknown instance does not require another lookup to count its native SIGNAL pins or nets.
fields=name,engineering.bbox_um,engineering.signal_pin_count,engineering.distinct_signal_net_count
retrieves the selected geometry and two different connection counts together.
S/objects/statistics accepts the SAME filters as objects and gives complete aggregation over matching objects;
For kind=instance, include_physical=1 also aggregates placed bbox areas and geometry coverage over ALL matches.
geometry.bbox_union_um is the complete filtered collection's bbox union. Grouping keeps object_count and overall
geometry in the SAME response, alongside each group's count/geometry; no separate ungrouped query is needed.
connected_to=<net>&net_role=load|driver uses distinct owning instances, excluding ports and counting each parent once.
For macro area and its core percentage use kind=instance&is_macro=1&include_physical=1:
geometry.total_bbox_area_um2, geometry.percent_of_core_area and geometry.core_bbox_um are direct facts.
Group rows include geometry statistics too; limit/offset only page the groups, never the overall aggregation.
Missing geometry is explicit; total area is null until every matched object's geometry is present.
Area is the sum of full object bboxes, including overlapping objects separately. Regional filters select whole objects.
group_by=master|kind|master_type|signal_type|driver_count|direction|is_macro. For regional counts use
kind=instance&group_by=is_macro&region=<xmin,ymin,xmax,ymax>&region_units=um&intersection=positive_area:
object_count counts ALL matching instances; group value 1 counts macros, 0 nonmacros, null unclassified.
For example kind=pin&parent_id=<instance>&group_by=signal_type
returns distinct SIGNAL/CLOCK/POWER/GROUND counts; never infer SIGNAL by merely excluding power.
For kind=net&group_by=signal_type, counts_by_signal_type and power_ground_net_count cover ALL matching nets
even when group rows are paged. The latter counts POWER+GROUND and is explicitly distinct from native isSpecial flags.

Engineering instance names preserve the stored name and also provide native_name without DEF escapes.
To retrieve the exact original spelling, use native queries against the original database; never invent its escape representation.
''',
    'timing': '''Path/point lists default to engineering facts with shared source references. Heavy repeated identity
Timing paths and points also expose explicit slack_ns/arrival_ns/required_ns/slew_ns/load_ff when extracted.
Data-point extrema carry max_value_ns for slew and max_value_ff for load; selected points carry slew_ns/arrival_ns/load_ff.
These fields are already ns/fF; do not rescale them. Original slack/arrival/slew/load/max_value remain SI s/F with their original sources.
Ranked S/timing-paths accepts tie_break=native_names to resolve equal values by full startpoint then endpoint ascending.
path_type=max|min filters by the actual native report type; max includes reported asynchronous groups.
For worst max/min headers use path_type=max|min&sort=slack&order=worst&limit=1 with selected header fields.
Default tie_break=report_order preserves source report order. Ranking metadata declares the actual tie rule.
reference maps, per-row evidence and path point-ID catalogs remain at detail=full; delivery.full_details
preserves this request's original filters/order/pagination. All points, names and numeric facts remain present.
S/timing-paths/<path_id>?fields=timing_path reads only the path header, without point pages;
fields=<dotted fields> selects requested content, delivery.full_details restores the complete response.
S/timing-overview?resolve=1&check=both runs ONE fresh query for setup and hold together.
checks.setup and checks.hold each contain their own paths/associations; limit applies to EACH check.
For just slack/arrival/required select fields=checks.setup.paths,checks.hold.paths.
For both checks, path_details and all other per-check aggregates also sit under checks.setup/checks.hold;
there is no top-level paths field. For ONE check, paths/path_details and aggregates sit at the top level.
S/timing-paths/<path_id>/clock-paths returns BOTH complete clock trees and the original path delay header,
in exact native report order/units. Original instance/net values (including null/empty/undeclared fields)
remain untouched; database mappings do not replace native report fields. This is one joined original-report read.
S/timing-paths?check=setup|hold&sort=slack&order=worst&limit=N returns ranked stored paths;
sort=arrival ranks the native data_arrival_time (SI seconds), independently of slack ranking.
selection states the complete matching stored-path count and returned ranks; filters and ranking apply BEFORE limit/offset.
truncated/next_offset mean more matching paths remain, not clipped fields on a returned worst path.
This covers the stored candidate set, not unsampled native paths; use a fresh native query for those.
fields selects ROW columns such as startpoint,endpoint,slack_ns; paths is not a row column on this endpoint.
S/timing-paths/<path_id>/endpoints joins both endpoints' native pin/connection, owning-instance placement/counts,
original timing-point fragments and source references. Report net/instance values remain separate from native facts.
Top-level ports have instance=null. Missing native mappings remain explicit; fields=path,endpoints.endpoint selects one end.
filters include startpoint, endpoint, group, source_clock, target_clock, corner; fields=path_id,startpoint,endpoint,group,slack projects only those fields.
S/timing-points?path_section=source_path&sort=slew|load|arrival&order=worst&limit=N ranks data points over all stored paths.
Optional path_id restricts a path; pin_name, instance_id, net_id and check=setup|hold filter occurrences.
Use pin_name together with path_id when a pin's timing on one particular path is needed;
fields=pin_name,net_name,slew,load,arrival,instance_id keeps results small.
Projected path/point facts retain deduplicated sources plus record_sources routes to every original locator/fragment;
selecting fewer fields does not remove their provenance. The source list covers the returned page.
For projected paths/points, source_detail=compact returns every record_id and shared evidence/fragments
URL templates instead of repeating two long URLs per row; URL-encode the record_id before substitution.
S/timing-context exposes all original clocks, analysis setup and producer identity. S/artifacts lists attached originals
and the original manifest (digests, flow/tool identity), with limit/offset.
S/timing-paths/<path_id>/context?detail=summary&relation_limit=2 bounds graph relationships and states truncation.
For field-based context budgets, request just the needed path fields and name the omitted fields with continuation routes.
S/compare/<other_snapshot>/timing-paths/<path_id>?to_path_id=... compares paths and scenarios;
S/compare/<other_snapshot>/metrics?name=... compares metrics. S/objects/<id>/context and S/nets/<id>/context
provide provenance-bearing related facts with detail=summary and relation_limit.
S/compare/<other_snapshot>/inventory?metrics=<raw key or suffix> returns complete native instance/net/SIGNAL-net
counts for both snapshots, their deltas and matching literal metric values from each stage's original reports.
The response explicitly distinguishes native inventory counts including fillers from the reported cell area;
reports retain substage identity rather than being relabeled final. Prefer this joined comparison over repeated inventories.
Add include_native_area=1 for the actual report_design_area values on BOTH selected databases,
native_area evidence and native_area_um2 delta. Earlier substage metrics remain separately labeled.
Selected original timing metric reports include analysis_command_excerpt from the corresponding original log;
these are actual estimate_parasitics/read_* commands with source line/byte positions, not the later snapshot's setup.
S/timing-paths/<path_id>/points?limit=N&offset=N&path_section=source_path&fields=pin_name,instance_id,net_id,net_name,cell_name,arrival,load,slew gives compact data points; omit fields/path_section for all facts/sections. It gives points by path_section (source_path is the data path;
source_clock_path/target_clock_path are clock paths); slew and arrival in seconds, load in Farads.
S/timing-paths/<path_id>/engineering gives joined data-side pins, instances, nets, master_counts and bbox union;
macro_count/standard_cell_count and instance_classification_coverage count COMPLETE distinct data-path instances,
excluding clocks and ignoring pages. Missing native classification/associations make class totals null, not zero.
Single-check timing-overview exposes the same class counts over its distinct union of selected path instances;
check=both preserves separate nested setup/hold domains.
data_pin_names is the COMPLETE ordered data path sequence, including repeated pins and excluding clocks,
independent of point pagination. fields=path,data_pin_names,data_path_pin_count,clock_points_excluded is compact.
data_path_increments sums adjacent source_path arrival differences over the COMPLETE original sequence.
cell_increment_ns is the sum for equal nonempty original report instance names; wire_increment_ns covers other pairs.
total_increment_ns excludes clock sections and time before the first data point; negative increments stay signed.
largest_increment gives both pins/point IDs, kind, value, and first-report-pair tie choice. Missing arrivals make totals null.
Select fields=data_path_increments for the summary; original points remain available for individual differences.
arrays are paged by limit/offset. Add include_routing=1 to obtain the full routing_layers_crossed union,
including both sides of every via on ALL data-path nets. This avoids querying their wire shapes individually.
data_point_extrema provides complete maximum slew/load, ALL tied pin_names, tie_count and selected_point,
independent of the returned point page. Use these complete statistics rather than estimating ties from a page.
For engineering and timing-overview, tie_rule=source_order selects the first original data-path occurrence;
name_asc/name_desc select the smallest/greatest full pin name (default name_desc). All tied pin_names remain available.
S/timing-overview?check=setup&limit=5&signal_type=SIGNAL gives selected paths, net_names (complete sorted union),
nets (ranked by fanout), instance_names (complete sorted union), common_instances and master_occurrences.
It also gives complete data_point_extrema over the selected paths. Add include_physical=1 to attach the selected extrema
pins' owning instance engineering facts. Use fields=paths,data_point_extrema to read only those complete results.
Selected points carry point_id, path_id and source references: S/records/timing_points/<point_id>/fragments returns
the actual small original point and native mapping, avoiding full-path context expansion for a single fact.
Prefer these joins/aggregations for multi-object analysis rather than repeatedly fetching individual objects.
Stored path lists are samples. S/timing-overview?resolve=1&check=setup|hold&startpoint=<native>&endpoint=<native>&limit=N
submits a FRESH native query and waits internally (wait_seconds=0..120, default120). Omit unneeded startpoint/endpoint/group filters.
It returns paths and their engineering aggregates in ONE operation, including paths outside the stored sample.
paths includes actual native data_arrival_time, required_time and slack in s; do not infer arrival by subtracting rounded fields.
include_path_details=1 adds ordered data_pin_names, all data instance_names/master_counts, net counts, instance_bbox_union_um and per-path extrema.
include_physical=1 adds complete data-instance geometry, bbox union/DBU and selected extrema's instance facts.
include_connectivity=1 joins driver/load names and complete counts for ranked nets; net_limit bounds ranked net rows,
connectivity_pin_limit controls each pin page (default5). net_names remains the COMPLETE sorted filtered net union.
signal_type filters actual native net types without changing missing-association status. Object facts come from the explicitly
recorded parent with identical original ODB digest and run/stage identity; timing values keep the new query snapshot identity.
Project needed fields; query_execution and object_facts_source preserve both sources. delivery.full_details addresses the resulting
snapshot WITHOUT submitting another job. If still pending or failed, inspect query_execution and the explicit continuation routes;
never substitute a stored sample for a failed native query. Existing child path engineering also joins those same parent facts.
For a following net/instance/objects read, use /snapshots/<object_facts_source.snapshot.snapshot_id> as S;
the resulting query snapshot holds timing results, while its exact cited parent holds the object inventory.
For explicit asynchronous operation, POST S/timing-queries
payload {"from_pin":"native start", "to_pin":"native end", "path_group":"optional group", "path_count":5,"endpoint_path_count":1}.
Omit unneeded filters. It returns run.run_id and a new snapshot_id; GET /timing-queries/<run_id>?wait_seconds=120 waits for completion in one tool operation; repeat if still running, not rapid polling.
Once succeeded, then query the snapshot_ids returned there. Both setup and hold paths are generated.
S/constraints returns effective SDC, declared clocks/delays and native check_setup coverage (not sampled path coverage).
original_constraints maps each staged input digest to every matching original SDC path in the producer manifest;
cite the requested stage's original file. Clock-source ports/pins are in the create_clock target or native STA query,
and are distinct from those file paths. A virtual clock has no source ports/pins.
port_delay_coverage gives INPUT/OUTPUT port_count, unique ports_with_explicit_delay_count and ports_without_explicit_delay_count;
ports_without_delay gives COMPLETE sorted names, including clock ports. Duplicate min/max/rise/fall declarations count each port once.
other_port_directions keeps INOUT separate. Missing explicit delay is a coverage fact, not by itself a violation.
kind=propagation returns clock propagation statements; kind=all pages every original non-comment SDC line
in original order, including statements beyond named-clock creation. Read later matching declarations too.
''',
    'physical': '''S/pins/<native name or id>/engineering gives original native pin position and bbox in dbu/um, source and getter basis.
instance joins its owning instance's placement/orientation, or null for a top-level port.
native_connection gives connected net ID/name/type and direction using the same original ODB.
Use fields=pin.position_um,pin.position_success,instance.orientation,native_connection.net_name for these facts together.
S/congestion?file=<declared eight-column native TSV>&layers=<comma-separated layers>&limit=N&offset=N
ranks ALL matching grid cells by overflow then utilization descending, natural layer/index ascending.
Returns capacity, usage, overflow, native grid bbox and source line, with complete layer counts/overflow totals.
Zero capacity uses utilization zero for ranking. fields can project compact facts; paging never changes full-domain counts.
ITerm uses getAvgXY; BTerm uses getFirstPinLocation. Check position_success; a failed getter has no coordinate value.
S/physical/<object_id>?routing_limit=1 gives location_dbu/location_um, orientation and bbox (dbu/um), or pageable routing with routing_offset;
location_basis explicitly identifies dbInst.getLocation. Objects with include_physical=1 carry the same location fields;
use these extracted placement facts rather than requerying dbInst.getOrigin for a different coordinate definition.
routing_limit=0 returns all geometry. S/nets/<native net name or net_id>/routing-summary gives full layer/via/centerline totals, wirelength_um and via_distribution_by_layer (each via counted on BOTH bottom and top layers).
For all metal layers used by a net, read routing_layers_used (union of segment_layers and via_layers),
not just keys of layers, which is the segment-length dictionary and excludes via-only participation.
S/routing-totals gives full-design geometric length/vias. S/nets/<net name or id>/parasitics?limit=N&offset=N
reads the original SPEF and gives total capacitance, RES sums, units, paged branches and source offsets.
S/violations reads native DRC reports, locations and relevant names. Report bbox coordinates are um;
convert named x_min/y_min/x_max/y_max boxes to [xmin,ymin,xmax,ymax] when the answer schema requests an array.
Specify file for a particular iteration report; final DRC count comes from the stage metric, not an earlier iteration.
''',
    'sources': '''S/artifacts/files lists all original report/log/result paths, categories and current size_bytes with complete paging.
Use detail=full or fields to recover producer_manifest_entry (literal original declared digest/size), timestamps and search directories.
Declared digests are separate from current sizes; this does not claim current bytes were rehashed. Absent manifest entries remain null.
S/artifacts/files/excerpt?path=<relative>&offset=0&max_bytes=8192 reads original bytes, including configs/libs declared by producer and receipts/<design>.flow.log etc.
S/artifacts/files/excerpt also accepts start_line=<1-based>&end_line=<inclusive> to retrieve specific original lines,
with exact source identity/byte positions and explicit range completion. Byte continuation remains available.
S/artifacts/files/search?path=<relative>&pattern=<regular expression>&ignore_case=1&context_lines=0&limit=20
searches ALL original lines and returns matching text, source digest, line numbers and byte offsets;
offset/next_offset page the matches. Use it for report/SDC/log facts beyond the compact endpoints.
S/artifacts/files/json?path=<original JSON file>&json_path=$.checks&sort_field=slack&order=asc&tie_fields=startpoint,endpoint&limit=1
tie_order=asc|desc controls equal-value tie fields independently of the main ranking; default asc.
For greatest pin name among equal slew/capacitance values, use order=desc&tie_fields=pin&tie_order=desc.
queries EVERY object row in that original array, not a stored sample. fields=startpoint,endpoint,slack selects literal source fields;
filters=<URL-encoded JSON object> applies exact typed row matches (for example {"path_type":"max"}). Dotted fields select nested objects.
Counts and ranking cover the full array before paging; source_array_indices identify exact original rows and source carries its digest.
Rows lacking a requested field keep it absent; explicit nulls remain null. delivery names fields absent from some returned rows.
Unknown fields absent from the complete source array are named errors; sparse report rows do not fail the whole projection.
For native report_checks JSON, literal time values use seconds; this raw-content query does not convert units or rerun timing.
Use original files for historical flow questions; fresh native queries remain distinct for saved-state reanalysis.
Discover exact relative source paths with S/artifacts/files; platform and stage filenames depend on the actual run.
S/sources/<artifact_id>/excerpt?offset=...&max_bytes=... reads attached originals; next_offset continues.
S/records/<record_type>/<record_id>/fragments retrieves original fragment evidence.
GET /runs/<run_id>/metrics?stage=<actual stage>&name=WNS filters a specific canonical metric; omit name for all metrics in that stage.
Use names=WS,WNS,TNS,HOLD_WS,HOLD_WNS,HOLD_TNS to get several exact names in one operation.
name_contains matches canonical names or original keys; include_raw=1 includes literal original metrics.
fields=name,value,unit,raw_key,value_basis,corner,status selects compact rows with deduplicated evidence at top level.
requested_names/missing_names refer to the full matching set, not just this page; next_offset continues pages.
GET /runs/<run_id>/metrics?include_raw=1 provides canonical and original metric keys.
The same name/stage/snapshot_id/scene filters apply to original keys. Request one exact raw key or canonical
STDCELL_COUNT/MACRO_COUNT/AREA/STDCELL_AREA/MACRO_AREA instead of reading an entire metric inventory.
Canonical rows carry raw_key, value_basis and quantity_scope; AREA is cell instance area, not die/core area.
POST /query payload {"requests":["/snapshots/...", "/runs/.../metrics?...", ...]} batches up to20 snapshot/run read paths.
Each actual failure stays visible in its result; failed_query_count reports failures and other independent reads continue.
For dependent reads, use {variable} in a later path and bindings:{"variable":{"request":0,"pointer":"/data/..."}}.
request is the zero-based EARLIER result index; pointer addresses that result's actual JSON, including its data wrapper.
Strings/numbers are URL-encoded automatically. Null/missing values or failed source reads cannot supply a binding.
This joins discovery, the discovered object's engineering facts and original evidence in ONE model tool call.
''',
    'native': '''For engineering facts beyond these queries, POST S/native-queries with payload {"script":"Tcl query","with_timing":false}.
For other original states, discover declared .odb paths with S/artifacts/files; extra_files:["<declared relative path>", ...]
stages those original files at their same relative paths. Set odb_file to the declared .odb path to query
that state instead of the snapshot ODB; OpenROAD cannot read_db twice into an already populated database.
For alternate-stage timing use with_timing=false and load that stage's declared libraries/SDC/SPEF in the script.
The original ODB is already loaded, so use set block [[[ord::get_db] getChip] getBlock]. For STA facts set with_timing=true
so the snapshot's original libraries/SDC/parasitics are loaded. Native master pin classification uses [$iterm getMTerm] getSigType.
GET /native-queries/<run_id>?wait_seconds=120 returns actual process output in excerpt.text and source artifact information;
continue with offset/max_bytes when excerpt.truncated. This is a real native query, not a stored question answer.
Public native responses default to the actual outcome/output without large execution/input inventories.
POST body detail="full" or GET detail=full reads complete execution/input metadata; delivery.full_details keeps the output offset/format.
S/instances/<name or id>/power runs fresh report_power -instances -format json -digits 9 using exact original native instance ID.
Returns power_w.internal,switching,leakage,total in W, reported_name and native_query.run_id/status. Optional scene=<actual native scene>.
It reconstructs the original libraries/clocks/RC; derived timing states resolve to the verified original object state. No stored power substituted.
Source excerpts default to text without duplicate base64; format=base64 returns exact original bytes, format=full returns both.
Failed native queries retain status=failed and expose the actual error report; read it to correct the Tcl method.
For placed ITerm coordinates, $iterm getAvgXY returns {success x y} in dbu; check success before using x/y.
Timing values from paths/points are s, loads F; stage timing metrics ns; power W; physical values dbu unless stated otherwise.
WNS is min(0,worst slack), so positive WS means WNS0. Keep analysis scenario (clock mode, parasitics, corner) explicit.

POST S/native-queries also accepts wait_seconds=120 and max_bytes=8192 in its JSON body.
This submits and waits in one request; if status is still running use the returned run_id to continue.
Snapshot timing_context.corner is the declared snapshot label, not a guaranteed native OpenSTA corner name.
Use report_units to read loaded STA units. For native corner names inspect the current engine's supported commands;
do not assume sta::corners exists or infer a named native corner from an empty query result.
Read excerpt.text for actual output, failure_details for actual errors, and excerpt's continuation when truncated.
''',
}

QUICK_GUIDES = {
    'run': '''Let S=/snapshots/<snapshot_id>; GET results are under data. URL-encode names/query values.
GET /snapshots?design_id={design}&origin=flow discovers original states; origin=query discovers supplementary results.
S/summary gives counts, core/die geometry and dbu_per_micron; fields selects dotted paths; detail=full restores all metadata.
S/run-inventory?stage=<actual stage>&metrics=<exact key or namespace components> reads matching metrics in ALL original stage reports.
Each original report/corner remains separately identified; missing index does not mean missing source data.
S/source-metadata?fields=run_origin,configuration,libraries,units exposes actual design/tool/input identity and loaded units.
S/timing-context gives declared clocks and analysis context. S/analysis-setup queries actual native units/scenes/corners.
Native timing s/F differs from stage metrics ns and library display units. Unknown version banners remain unknown.
Read the full guide for source manifests, corner selection and complete availability details.''',
    'objects': '''Let S=/snapshots/<snapshot_id>; URL-encode all native names. GET results are under data.
S/objects?kind=instance|pin|net supports exact name, name_contains, parent_instance (pins), master, is_macro,
direction, signal_type, connected_to=<net>&net_role=load|driver, and region=xmin,ymin,xmax,ymax&region_units=um.
intersection=positive_area excludes mere touching. sort=name|fanout|bbox_area&order=asc|desc ranks before limit/offset.
include_physical=1 joins each returned object's bbox; include_engineering=1 joins instance engineering/pin classification.
S/objects/statistics?kind=instance&group_by=is_macro|master&include_physical=1 gives COMPLETE counts and overall/group geometry.
Count/sum/bbox are independent of pages. Missing geometry/classification is partial, not zero. fields selects needed facts.
S/instances/<name>/engineering: instance.bbox_um,instance.orientation,native_pin_classification (pin OWN type).
S/instances/<name>/pin-inventory?pin_type=SIGNAL&direction=INPUT returns filtered native pins with complete counts/paging.
Add net_sort=load_count for COMPLETE distinct-net rankings and receiving_macro_count. Returned pin names retain full/local forms.
S/nets/<name>/engineering gives all driver/load COUNTS with sorted paged driver_pins/load_pins.
traverse=1 adds COMPLETE driver_traversal/load_traversal.pin_names and internal_instance_count (distinct parents; ports excluded).
include_instances=1&include_physical=1 adds complete driver_instances/load_instances count,geometry,groups by is_macro.
These geometry/class totals cover all matching distinct owners, regardless of pin/instance pages; instance_is_macro filters owners.
S/instances/<name>/pair?with_instance=<other>&signal_type=SIGNAL returns geometry.bbox_center_manhattan_um and complete shared_nets.
S/instances|pins|nets/<name>/provenance gives original native identity, database/source digests and locators.
Use limit/offset/next_offset to continue complete lists. Full help describes all filters and schemas.''',
    'timing': '''Let S=/snapshots/<snapshot_id>; URL-encode names; GET results are under data.
S/timing-paths?path_type=max|min&sort=slack&order=worst&tie_break=native_names&limit=N
returns ranked STORED samples (twenty/group). tie_break=native_names orders equal values by startpoint,endpoint;
report_order preserves original row order. Native max/min includes the report's asynchronous checks.
fields=path_id,startpoint,endpoint,slack_ns,arrival_ns,required_ns projects header rows. Missing sampled endpoints need native completion.
S/timing-paths/<path_id>/engineering joins the COMPLETE data path; select fields=instance_count,net_count,
instance_bbox_union_um,macro_count,standard_cell_count,instance_classification_coverage for full placement/class counts.
Counts exclude clock sections and duplicate instances and ignore output pages. Partial classification gives null class totals.
Other selectable fields: data_pin_names (complete ordered sequence),master_counts,data_point_extrema,data_path_increments.
Extrema tie_rule=source_order|name_asc|name_desc; source_order chooses the first original point among numeric ties.
data_path_increments returns adjacent source_path cell/wire sums and largest pair, excluding clocks/time before first point.
S/timing-overview?check=setup|hold&limit=N joins selected path headers and instance/net unions.
S/timing-overview?resolve=1&check=setup|hold&startpoint=<pin>&endpoint=<pin>&limit=1
runs a FRESH original-state native analysis, waits internally and returns paths in ONE read (including outside the sample).
For ONE check, fields uses TOP LEVEL paths,instance_union_count,net_union_count,macro_count,standard_cell_count,data_point_extrema.
include_physical=1 adds instance_bbox_union_um. include_path_details=1 adds path_details.data_pin_names,
path_details.master_counts,path_details.data_path_increments and per-path counts/extrema. Request only needed fields.
For check=both, all those per-check fields are NESTED: fields=checks.setup.paths,checks.hold.paths;
for detailed setup increments use checks.setup.path_details.data_path_increments. There is NO top-level paths for both.
Both checks come from one fresh job; limit applies to EACH. inspect query_execution and continue pending jobs without resubmission.
After a fresh query, timing results use its child snapshot; subsequent object/net/instance reads use
/snapshots/<object_facts_source.snapshot.snapshot_id>, which cites the exact original database, run and stage.
Explicit labeled *_ns/load_ff fields are already ns/fF; original report timing/capacitance fields remain s/F.
S/constraints gives declared/effective constraints, native check_setup and complete port-delay coverage; missing delay is not proof of violation.
Use help topic=sources for FULL original report-array queries, topic=native for arbitrary native queries; detail=full restores all timing help.''',
    'physical': '''Let S=/snapshots/<snapshot_id>; URL-encode native names. GET results are under data.
S/objects?kind=instance&include_physical=1 joins native placement geometry; fields selects needed columns.
S/objects/statistics?kind=instance&region=xmin,ymin,xmax,ymax&region_units=um&intersection=positive_area
counts the COMPLETE matching domain; include_physical=1 gives full bbox union/area; group_by=is_macro splits native types.
S/pins/<name>/engineering?fields=pin.position_success,pin.position_um,instance.orientation,native_connection.net_name
gives transformed native pin coordinates, owning orientation and actual connection in one read. Check position_success.
S/nets/<name>/routing-summary gives full indexed native segment/via lengths and per-layer totals.
routing_layers_used includes segment and via-only layers; each via participates once on BOTH top/bottom layers.
S/nets/<name>/parasitics reads original SPEF with units/full counts and branch paging.
S/congestion?file=<declared eight-column TSV>&layers=<actual layers>&limit=N ranks ALL matching original grid cells;
ranking is overflow/utilization descending, then natural layer/x/y index ascending; zero-capacity utilization is zero.
fields selects cells/counts/sources; output paging never limits complete grid totals.
S/violations gives report locations/related names. Native ODB dbu converts with dbu_per_micron; *_um fields are already um.
Full help explains original-source availability, placement-location basis and routing continuation.''',
    'sources': '''Let S=/snapshots/<snapshot_id>; GET results are under data; URL-encode paths/query values.
S/artifacts/files discovers ALL declared original report/log/result paths with limit/offset continuation.
S/artifacts/files/excerpt?path=<relative>&max_bytes=8192&offset=0 reads original bytes; continue next_offset.
start_line/end_line select exact inclusive lines. S/artifacts/files/search?path=<relative>&pattern=<regex>
searches ALL original lines; context_lines/limit/offset control returned matches, not search coverage.
S/artifacts/files/json?path=<original JSON>&json_path=$.checks&sort_field=slack&order=asc&tie_fields=startpoint,endpoint&limit=1
queries the FULL original array before paging, not a stored path sample. filters=<JSON object> selects exact typed row values;
fields selects literal source fields; tie_order=asc|desc orders equal-value tie fields. Units remain original; absent fields stay absent.
S/records/<record_type>/<record_id>/fragments returns original point/object evidence without full context expansion.
GET /runs/<run_id>/metrics?stage=<actual stage>&names=WS,WNS,TNS reads needed canonical metrics with original raw keys and units.
include_raw=1 also reads original keys; source reports/corners stay distinct. Cell area differs from die/core area.
POST /query {"requests":["<GET path>","<GET path>"]} batches independent reads; per-request failures remain visible.
Dependent bindings use {"key":{"request":0,"pointer":"/data/<JSON pointer>"}} and {key} in later paths.
Full help explains available source filters, corner selection, evidence fields and complete chunk recovery.''',
    'native': '''Let S=/snapshots/<snapshot_id>; POST S/native-queries
{"script":"Tcl query","with_timing":false,"wait_seconds":120,"max_bytes":8192} runs and waits for REAL native OpenROAD.
Original ODB is already loaded: set block [ord::get_db_block]. with_timing=true also reconstructs original libraries/SDC/clocks/RC.
Read status, excerpt.text and failure_details. If still running, GET /native-queries/<run_id>?wait_seconds=120;
continue output with offset/max_bytes when excerpt.truncated. Do not submit a second job just to wait/read existing output.
Defaults keep actual output/errors compact. POST detail="full" or GET detail=full retrieves execution/input inventories.
S/instances/<name or id>/power gives fresh power_w.internal,switching,leakage,total in W without writing Tcl or escaping native names.
Optional scene selects an actual native scene; default uses original analysis. Raw native report remains at native_query.run_id.
For another actual stage, discover original files via artifacts/files and use odb_file plus extra_files.
Do not read_db again into the populated database. Alternate-stage timing must load that stage's own analysis context.
Native getAvgXY returns {success x y} in dbu. Check success, divide x/y by native getDbUnitsPerMicron.
Original native timing JSON is s/F; library display units may be ps/fF. Use actual report_units, not guessed corner/clock units.
WNS=min(0,worst slack). Failed native queries retain their real errors; missing facts are not zeros.
Use timing-overview?resolve=1 for joined directed-path queries. Full help gives alternate inputs, setup and continuation details.''',
}

def api_help(store, snapshot_id, query):
    snapshot = store.snapshot(snapshot_id)
    topic = query.get('topic')
    base = '/snapshots/' + snapshot_id
    if topic is None:
        return {'snapshot_id': snapshot_id, 'usage': 'S=' + base + '; URL-encode object names/query values; GET results are in data',
                'topics': [{'topic': key, 'description': value, 'path': base + '/help?topic=' + key}
                           for key, value in TOPICS.items()]}
    if topic not in GUIDES:
        raise ValueError('help topic must be ' + '|'.join(GUIDES))
    detail = query.get('detail', 'summary')
    if detail not in ('summary', 'full'):
        raise ValueError('help detail must be summary|full')
    guide = (GUIDES if detail == 'full' else QUICK_GUIDES)[topic]
    guide = guide.replace('{design}', snapshot['design_id']).replace('{variant}', snapshot['revision_id']).replace('{snapshot_id}', snapshot_id)
    return {'snapshot_id': snapshot_id, 'topic': topic, 'detail': detail, 'guide': guide,
            'full_details': base + '/help?topic=' + topic + '&detail=full', 'topic_index': base + '/help'}

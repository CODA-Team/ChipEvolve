"""Native OpenROAD engineering calculations and parsing."""
import base64
import re

def _parse(text):
    rows, totals = [], []
    for line in text.splitlines():
        if line.startswith('EDA_PIN_TOTAL '):
            totals.append(int(line.split()[1]))
        if not line.startswith('EDA_PIN\t'):
            continue
        fields = line.split('\t')
        if len(fields) != 7:
            raise ValueError('native pin inventory row is malformed')
        _, native_id, local, pin_type, direction, net, net_type = fields
        if not native_id.isdecimal() or int(native_id) <= 0:
            raise ValueError('native pin inventory ID is invalid')
        native_net = base64.b64decode(net, validate=True).decode() if net else None
        rows.append({'native_id': native_id,
            'local_name': base64.b64decode(local, validate=True).decode(),
            'native_pin_signal_type': pin_type, 'direction': direction,
            'net_name': native_net.replace('\\', '') if native_net is not None else None,
            'net_native_name': native_net,
            'connected_net_signal_type': net_type or None})
    if len(totals) != 1 or totals[0] != len(rows) or len({r['native_id'] for r in rows}) != len(rows):
        raise ValueError('native pin inventory is incomplete or has duplicate pins')
    return sorted(rows, key=lambda r: r['local_name'])


def ranking_script(query):
    if query.get('net_sort') != 'load_count':
        raise ValueError('net_sort must be load_count')
    pin_type, direction = query.get('pin_type', ''), query.get('direction', '')
    if pin_type not in ('', 'SIGNAL', 'CLOCK', 'POWER', 'GROUND'):
        raise ValueError('pin_type must be SIGNAL|CLOCK|POWER|GROUND')
    if direction not in ('', 'INPUT', 'OUTPUT', 'INOUT'):
        raise ValueError('direction must be INPUT|OUTPUT|INOUT')
    return '''set selected_nets [dict create]
foreach p [$i getITerms] {
    set m [$p getMTerm]; set n [$p getNet]
    if {$n eq "NULL"} {continue}
    if {"PIN_TYPE" ne "" && [$m getSigType] ne "PIN_TYPE"} {continue}
    if {"DIRECTION" ne "" && [$m getIoType] ne "DIRECTION"} {continue}
    dict set selected_nets [$n getId] $n
}
puts "EDA_NET_TOTAL [dict size $selected_nets]"
foreach n [dict values $selected_nets] {
    set loads 0; set macros [dict create]; set receivers [dict create]; set drivers [list]
    foreach p [$n getITerms] {
        if {[[$p getMTerm] getIoType] eq "OUTPUT"} {
            lappend drivers "[[$p getInst] getName]/[[$p getMTerm] getName]"
            continue
        }
        incr loads
        set receiver [$p getInst]
        dict set receivers [$receiver getId] 1
        if {[[$receiver getMaster] isBlock]} {dict set macros [$receiver getId] 1}
    }
    foreach p [$n getBTerms] {
        if {[$p getIoType] eq "INPUT"} {lappend drivers [$p getName]} else {incr loads}
    }
    puts [join [list EDA_NET [$n getId] [binary encode base64 -maxlen 0 [$n getName]] \
        $loads [dict size $macros] [dict size $receivers] [llength $drivers]] "\\t"]
    foreach pin $drivers {
        puts [join [list EDA_NET_DRIVER [$n getId] [binary encode base64 -maxlen 0 $pin]] "\\t"]
    }
}'''.replace('PIN_TYPE', pin_type).replace('DIRECTION', direction)


def pin_inventory_script(native_id):
    script = '''set b [ord::get_db_block]
set i [odb::dbInst_getInst $b NATIVE_ID]
if {$i eq "NULL"} {error "original instance not found"}
puts "EDA_PIN_TOTAL [llength [$i getITerms]]"
foreach p [$i getITerms] {
    set m [$p getMTerm]
    set n [$p getNet]
    set name {}; set type {}
    if {$n ne "NULL"} {set name [$n getName]; set type [$n getSigType]}
    puts [join [list EDA_PIN [$p getId] [binary encode base64 -maxlen 0 [$m getName]] \
        [$m getSigType] [$m getIoType] [binary encode base64 -maxlen 0 $name] $type] "\\t"]
}'''.replace('NATIVE_ID', native_id)
    return script

def pin_geometry_script(kind, native_id):
    cls, getter = ('dbITerm', 'getAvgXY') if kind == 'iterm' else ('dbBTerm', 'getFirstPinLocation')
    script = '\n'.join([
        'set b [[[ord::get_db] getChip] getBlock]',
        f'set p [odb::{cls}_get{cls[2:]} $b {native_id}]',
        f'puts "EDA_PIN_POSITION [$p {getter}]"',
        'set box [$p getBBox]',
        'puts "EDA_PIN_BBOX [$box xMin] [$box yMin] [$box xMax] [$box yMax]"'])
    return (cls, getter, script)

def parse_pin_geometry(text, truncated=False):
    position = re.search(r'^EDA_PIN_POSITION ([01]) (-?\d+) (-?\d+)\s*$', text, re.M)
    box = re.search(r'^EDA_PIN_BBOX (-?\d+) (-?\d+) (-?\d+) (-?\d+)\s*$', text, re.M)
    if position is None or box is None or truncated:
        raise ValueError('native pin geometry report is incomplete or malformed')
    coordinates = [int(v) for v in position.groups()[1:]] if position[1] == '1' else None
    bbox = [int(v) for v in box.groups()]
    if bbox[0] > bbox[2] or bbox[1] > bbox[3]:
        raise ValueError('native pin bounding box is invalid')
    return coordinates, bbox

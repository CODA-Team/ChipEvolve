"""Complete native net rankings for filtered instance pins, before pagination."""
import base64

from .queries import _limit, _offset, _page


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


def ranked_nets(text, query):
    rows, totals, drivers = [], [], {}
    for line in text.splitlines():
        if line.startswith('EDA_NET_TOTAL '):
            totals.append(int(line.split()[1]))
        if line.startswith('EDA_NET_DRIVER\t'):
            fields = line.split('\t')
            if len(fields) != 3 or not fields[1].isdecimal():
                raise ValueError('native driver row is malformed')
            drivers.setdefault(fields[1], []).append(base64.b64decode(fields[2], validate=True).decode())
        if not line.startswith('EDA_NET\t'):
            continue
        fields = line.split('\t')
        if len(fields) != 7 or any(not fields[i].isdecimal() for i in (1, 3, 4, 5, 6)):
            raise ValueError('native net ranking row is malformed')
        native = base64.b64decode(fields[2], validate=True).decode()
        rows.append({'native_id': fields[1], 'native_name': native,
                     'name': native.replace('\\', ''), 'load_count': int(fields[3]),
                     'receiving_macro_count': int(fields[4]),
                     'receiving_instance_count': int(fields[5]), 'driver_count': int(fields[6])})
    if len(totals) != 1 or totals[0] != len(rows) or len({r['native_id'] for r in rows}) != len(rows):
        raise ValueError('native net ranking is incomplete or duplicated')
    if set(drivers) - {row['native_id'] for row in rows}:
        raise ValueError('native driver references an unselected net')
    for row in rows:
        native = drivers.get(row['native_id'], [])
        if len(native) != row['driver_count'] or len(set(native)) != len(native):
            raise ValueError('native net drivers are incomplete or duplicated')
        row['native_drivers'] = sorted(native)
        row['drivers'] = sorted(pin.replace('\\', '') for pin in native)
    rows.sort(key=lambda row: (-row['load_count'], row['name']))
    for rank, row in enumerate(rows, 1):
        row['rank'] = rank
    limit, offset = _limit(query), _offset(query)
    return {'nets': rows[offset:offset + limit],
            'order': 'load_count descending, unescaped native name lexicographically ascending',
            'coverage_scope': 'all distinct nets on filtered native instance pins; counts and ranking before pagination',
            'load_count_basis': 'native ITerms other than OUTPUT plus native BTerms other than INPUT',
            'receiving_macro_count_basis': 'distinct receiving native instances whose master.isBlock is true; ports excluded',
            'receiving_instance_count_basis': 'distinct native owners of load ITerms; ports excluded; INOUT is a load',
            'driver_basis': 'all native OUTPUT ITerms and INPUT BTerms; native_drivers retain exact spelling',
            **_page(len(rows), len(rows[offset:offset + limit]), limit, offset)}

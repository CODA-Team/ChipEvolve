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
    set loads 0; set macros [dict create]
    foreach p [$n getITerms] {
        if {[[$p getMTerm] getIoType] eq "OUTPUT"} {continue}
        incr loads
        set receiver [$p getInst]
        if {[[$receiver getMaster] isBlock]} {dict set macros [$receiver getId] 1}
    }
    foreach p [$n getBTerms] {if {[$p getIoType] ne "INPUT"} {incr loads}}
    puts [join [list EDA_NET [$n getId] [binary encode base64 -maxlen 0 [$n getName]] \
        $loads [dict size $macros]] "\\t"]
}'''.replace('PIN_TYPE', pin_type).replace('DIRECTION', direction)


def ranked_nets(text, query):
    rows, totals = [], []
    for line in text.splitlines():
        if line.startswith('EDA_NET_TOTAL '):
            totals.append(int(line.split()[1]))
        if not line.startswith('EDA_NET\t'):
            continue
        fields = line.split('\t')
        if len(fields) != 5 or any(not fields[i].isdecimal() for i in (1, 3, 4)):
            raise ValueError('native net ranking row is malformed')
        native = base64.b64decode(fields[2], validate=True).decode()
        rows.append({'native_id': fields[1], 'native_name': native,
                     'name': native.replace('\\', ''), 'load_count': int(fields[3]),
                     'receiving_macro_count': int(fields[4])})
    if len(totals) != 1 or totals[0] != len(rows) or len({r['native_id'] for r in rows}) != len(rows):
        raise ValueError('native net ranking is incomplete or duplicated')
    rows.sort(key=lambda row: (-row['load_count'], row['name']))
    limit, offset = _limit(query), _offset(query)
    return {'nets': rows[offset:offset + limit],
            'order': 'load_count descending, unescaped native name lexicographically ascending',
            'coverage_scope': 'all distinct nets on filtered native instance pins; counts and ranking before pagination',
            'load_count_basis': 'native ITerms other than OUTPUT plus native BTerms other than INPUT',
            'receiving_macro_count_basis': 'distinct receiving native instances whose master.isBlock is true; ports excluded',
            **_page(len(rows), len(rows[offset:offset + limit]), limit, offset)}

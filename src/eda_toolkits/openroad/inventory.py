"""Native OpenROAD inventory commands and parsing."""
import re

def net_inventory_script():
    script = '''set b [[[ord::get_db] getChip] getBlock]
set total 0
set special 0
set types [dict create]
foreach n [$b getNets] {
    incr total
    if {[$n isSpecial]} {incr special}
    dict incr types [$n getSigType]
}
puts "EDA_NET_TOTAL $total"
puts "EDA_NET_SPECIAL $special"
dict for {type count} $types {puts "EDA_NET_TYPE $type $count"}
'''
    return script


def parse_net_inventory(text, truncated=False):
    total = re.findall(r'^EDA_NET_TOTAL (\d+)\s*$', text, re.M)
    special = re.findall(r'^EDA_NET_SPECIAL (\d+)\s*$', text, re.M)
    types = re.findall(r'^EDA_NET_TYPE (\w+) (\d+)\s*$', text, re.M)
    counts = {kind: int(count) for kind, count in types}
    if (truncated or len(total) != 1 or len(special) != 1
            or len(counts) != len(types) or sum(counts.values()) != int(total[0])
            or int(special[0]) > int(total[0])):
        raise ValueError('native net inventory report is incomplete or malformed')
    return int(total[0]), int(special[0]), counts

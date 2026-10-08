"""Native OpenROAD engineering calculations and parsing."""
import base64
import json
import math
import re

def instance_power_script(native_id, scene=None):
    script = '''set b [ord::get_db_block]
set i [odb::dbInst_getInst $b NATIVE_ID]
if {$i eq "NULL"} {error "original instance not found"}
set native_name [$i getName]
set cell [sta::find_instance $native_name]
if {$cell eq "NULL"} {error "original instance has no exact STA instance"}
set mapped [sta::sta_to_db_inst $cell]
if {$mapped eq "NULL" || [$mapped getId] != [$i getId]} {error "STA instance does not match original native ID"}
puts "EDA_INSTANCE_POWER_BEGIN"
report_power -instances $cell -format json -digits 9 SCENE
puts "EDA_INSTANCE_POWER_END"
'''.replace('NATIVE_ID', native_id)
    scene_argument = ''
    if scene is not None:
        encoded = base64.b64encode(scene.encode()).decode()
        scene_argument = '-scene [binary decode base64 {' + encoded + '}]'
    script = script.replace('SCENE', scene_argument)
    return script

def parse_instance_power(text, expected_name, run_id):
    blocks = re.findall(r'^EDA_INSTANCE_POWER_BEGIN\s*\n(.*?)\nEDA_INSTANCE_POWER_END\s*$', text, re.M | re.S)
    if len(blocks) != 1:
        raise ValueError('native instance power report is incomplete or malformed; run ' + run_id)
    # OpenSTA emits literal identifier escapes in name fields. Consume complete
    # escape tokens so a valid doubled backslash is never repaired a second time.
    # This boundary normalization leaves numbers and the retained report intact;
    # JSON decoding remains the standard decoder, not another response envelope.
    def quote_native_name(match):
        name = re.sub(r'\\.', lambda token: token[0] if token[0][1] in '"\\/bfnrtu'
                      else '\\' + token[0], match[2])
        return match[1] + name + match[3]
    document = re.sub(r'("name"\s*:\s*")((?:\\.|[^"\\])*)(")',
                      quote_native_name, blocks[0])
    try:
        reports = json.loads(document)
    except json.JSONDecodeError as error:
        raise ValueError('native instance power report could not be read; original completed report at /native-queries/'
                         + run_id + ': ' + str(error)) from error
    if (not isinstance(reports, list) or len(reports) != 1 or not isinstance(reports[0], dict)
            or not isinstance(reports[0].get('name'), str)
            or reports[0]['name'].replace('\\', '') != expected_name.replace('\\', '')):
        raise ValueError('native instance power report is not the requested original instance; run ' + run_id)
    report = reports[0]
    keys = ('internal', 'switching', 'leakage', 'total')
    if any(not isinstance(report.get(k), (float, int)) or isinstance(report[k], bool)
           or not math.isfinite(report[k]) for k in keys):
        raise ValueError('native instance power report lacks finite original values; run ' + run_id)
    return report

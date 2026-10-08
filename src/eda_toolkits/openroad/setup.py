"""Native OpenROAD setup getters and parsing."""
import re

def analysis_setup_script():
    script = '''puts "EDA_SETUP_UNITS_BEGIN"
report_units
puts "EDA_SETUP_UNITS_END"
foreach scene [get_scenes *] {puts "EDA_SETUP_SCENE [get_full_name $scene]"}
foreach corner [get_analysis_corners *] {puts "EDA_SETUP_CORNER [sta::analysis_corner_name $corner]"}
foreach library [get_libs *] {puts "EDA_SETUP_LIBRARY [get_full_name $library]"}
puts "EDA_SETUP_COMMAND_CORNER [sta::cmd_analysis_corner]"
puts "EDA_SETUP_COMPLETE"
'''
    return script


def parse_analysis_setup(text, truncated=False):
    units = re.findall(r'^EDA_SETUP_UNITS_BEGIN\n(.*?)^EDA_SETUP_UNITS_END\s*$', text, re.M | re.S)
    command = re.findall(r'^EDA_SETUP_COMMAND_CORNER (.+)$', text, re.M)
    if len(units) != 1 or len(command) != 1 or not re.search(r'^EDA_SETUP_COMPLETE\s*$', text, re.M) or truncated:
        raise ValueError('native analysis setup report is incomplete or malformed')
    unit_rows = re.findall(r'^\s*(time|capacitance|resistance|voltage|current|power|distance)\s+(\S+)\s*$', units[0], re.M)
    if len(unit_rows) != 7 or len(dict(unit_rows)) != 7:
        raise ValueError('native report_units must declare all seven original UI unit families')
    return dict(native_ui_units=dict(unit_rows),
        scene_names=re.findall(r'^EDA_SETUP_SCENE (.+)$', text, re.M),
        explicit_analysis_corner_names=re.findall(r'^EDA_SETUP_CORNER (.+)$', text, re.M),
        loaded_liberty_names=re.findall(r'^EDA_SETUP_LIBRARY (.+)$', text, re.M),
        command_analysis_corner=command[0],
        )

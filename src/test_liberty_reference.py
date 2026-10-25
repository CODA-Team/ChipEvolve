"""The expert's reference uses the same libraries and units as physical STA."""

import gzip

import extract_liberty_tables as tables
import pytest


def liberty(*, time_unit="1ns", cap_unit="pf", name="BUF_X1"):
    timing = "\n".join(
        f"""{kind} (table) {{
          index_1 ("0.01, 0.03");
          index_2 ("0.001, 0.005");
          values ("0.01, 0.02", "0.03, 0.04");
        }}"""
        for kind in ("cell_rise", "cell_fall", "rise_transition", "fall_transition")
    )
    return f'''library (bound) {{
      time_unit : "{time_unit}";
      capacitive_load_unit (1,{cap_unit});
      cell ({name}) {{
        pin (A) {{ direction\t: input; capacitance : 0.002; }}
        pin (Z) {{ direction\t: output; timing () {{ {timing} }} }}
      }}
    }}'''


def test_explicit_library_ignores_unselected_asap7_and_converts_units(
    tmp_path, monkeypatch
):
    selected = tmp_path / "selected Nangate.lib"
    selected.write_text(liberty())
    (tmp_path / "asap7_INVBUF_RVT_FF.lib").write_text(liberty(name="BUFx2_ASAP7_75t_R"))
    monkeypatch.setattr(tables, "LIB_DIR", tmp_path)
    monkeypatch.setenv("TIMINGECO_LIB_FILES", str(selected))
    data = tables.extract_all()
    assert set(data["BUF"]) == {"BUF_X1"}
    cell = data["BUF"]["BUF_X1"]
    assert cell["input_cap_ff"] == pytest.approx(2)
    assert cell["delay_grid"][0][1] == pytest.approx(20)
    assert cell["delay_grid"][1][1] == pytest.approx(40)
    assert cell["slew_grid"][1][1] == pytest.approx(40)
    reference = tables.format_reference(data)
    assert "ASAP7" not in reference
    assert "VT swap:" not in reference
    assert "BUF_X1" in reference


def test_gzip_and_ps_ff_preserve_native_reference_units(tmp_path, monkeypatch):
    path = tmp_path / "selected.lib.gz"
    with gzip.open(path, "wt") as stream:
        stream.write(liberty(time_unit="1ps", cap_unit="ff"))
    monkeypatch.setenv("TIMINGECO_LIB_FILES", str(path))
    data = tables.extract_all()
    assert data["BUF"]["BUF_X1"]["input_cap_ff"] == pytest.approx(0.002)


def test_missing_explicit_library_does_not_fall_back(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMINGECO_LIB_FILES", str(tmp_path / "missing.lib"))
    with pytest.raises(FileNotFoundError):
        tables.extract_all()


def test_explicit_library_without_usable_cells_is_not_a_success(tmp_path, monkeypatch):
    path = tmp_path / "empty.lib"
    path.write_text(
        'library (empty) { time_unit : "1ns"; capacitive_load_unit (1,pf); }'
    )
    monkeypatch.setenv("TIMINGECO_LIB_FILES", str(path))
    with pytest.raises(ValueError, match="usable"):
        tables.extract_all()

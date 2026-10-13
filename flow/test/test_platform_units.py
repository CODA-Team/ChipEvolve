"""Physical clock identity remains the same at the native/public boundary."""
import pytest

from platform_leaf import native_evaluation


@pytest.mark.parametrize('platform,clock,expected,unit', [
    ('asap7', '310', .310, 'ps'),
    ('nangate45', '.792', .792, 'ns'),
])
def test_native_reference_clock_has_declared_units(platform, clock, expected, unit):
    row = native_evaluation(platform, clock, 'clk', ['actual.lib'])
    assert row['cp0_ns'] == pytest.approx(expected)
    assert row['source_time_unit'] == unit
    assert row['clock_port'] == 'clk'
    assert row['library_patterns'] == ['actual.lib']

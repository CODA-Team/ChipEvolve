from pathlib import Path

import pytest

from query_agent.adapters.design_data import FixtureDesignDataProvider
from query_agent.domain.design import DesignRegion
from query_agent.domain.query import QueryContext


def context() -> QueryContext:
    return QueryContext(workspace=Path("/workspace"), design_id="gcd")


def test_fixture_provider_returns_typed_objects_and_relationships() -> None:
    provider = FixtureDesignDataProvider()
    instance = provider.get_instance(context(), "u1")
    assert instance is not None
    assert instance.cell_type == "NAND2_X1"
    net = provider.get_net(context(), "n1")
    assert net is not None
    assert provider.get_fanout(context(), net.ref)[0].ref.name == "u2/A"
    assert provider.get_location(context(), instance.ref) == instance.location


def test_fixture_provider_rejects_a_different_design_scope() -> None:
    provider = FixtureDesignDataProvider()
    other = QueryContext(workspace=Path("/workspace"), design_id="other")
    assert provider.get_instance(other, "u1") is None


def test_region_bounds_are_validated() -> None:
    with pytest.raises(ValueError):
        DesignRegion(x_min=2, y_min=0, x_max=1, y_max=1, units="um")


def test_region_query_returns_only_objects_in_bounds() -> None:
    provider = FixtureDesignDataProvider()
    items = provider.get_instances_in_region(
        context(), DesignRegion(x_min=0, y_min=0, x_max=20, y_max=30, units="um")
    )
    assert [item.ref.name for item in items] == ["u1"]

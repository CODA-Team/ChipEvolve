from pathlib import Path

from query_agent.adapters.design_data import UnavailableDesignDataProvider
from query_agent.domain.query import QueryContext


def test_design_data_provider_is_explicitly_unavailable() -> None:
    provider = UnavailableDesignDataProvider()
    assert provider.capabilities == frozenset()
    assert (
        provider.query(
            "which instances drive net n1?", QueryContext(workspace=Path("/w"))
        )
        == ()
    )

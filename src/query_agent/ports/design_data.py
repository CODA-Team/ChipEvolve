"""Future design-data port."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from query_agent.domain.capability import Capability
from query_agent.domain.design import (
    DesignConnection,
    DesignInstance,
    DesignLocation,
    DesignNet,
    DesignObjectRef,
    DesignPin,
    DesignRegion,
)
from query_agent.domain.query import QueryContext


class DesignDataProvider(Protocol):
    """Port for the future structured design-data foundation."""

    @property
    def capabilities(self) -> frozenset[Capability]:
        """Capabilities supported by the connected data foundation."""

        ...

    def get_instance(self, context: QueryContext, name: str) -> DesignInstance | None:
        """Return one typed instance by canonical name."""

        ...

    def get_net(self, context: QueryContext, name: str) -> DesignNet | None:
        """Return one typed net by canonical name."""

        ...

    def get_pin(self, context: QueryContext, name: str) -> DesignPin | None:
        """Return one typed pin by canonical name."""

        ...

    def get_connections(
        self, context: QueryContext, object_ref: DesignObjectRef
    ) -> Sequence[DesignConnection]:
        """Return typed connections for one object."""

        ...

    def get_fanout(
        self, context: QueryContext, net_ref: DesignObjectRef
    ) -> Sequence[DesignPin]:
        """Return typed sink pins for one net."""

        ...

    def get_location(
        self, context: QueryContext, instance_ref: DesignObjectRef
    ) -> DesignLocation | None:
        """Return the location of one typed instance."""

        ...

    def get_instances_in_region(
        self, context: QueryContext, region: DesignRegion
    ) -> Sequence[DesignInstance]:
        """Return typed instances whose locations fall in a region."""

        ...

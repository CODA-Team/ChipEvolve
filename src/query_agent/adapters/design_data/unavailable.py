"""Explicit null implementation until the data foundation is available."""

from __future__ import annotations

from collections.abc import Sequence

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


class UnavailableDesignDataProvider:
    """A truthful provider with no design-data capability.

    Returning no evidence lets the application produce ``NEEDS_MORE_DATA`` or
    ``UNSUPPORTED`` as a normal business result. It never invents a parsed
    design object and it never raises for ordinary unavailability.
    """

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset()

    def get_instance(self, context: QueryContext, name: str) -> DesignInstance | None:
        del context, name
        return None

    def get_net(self, context: QueryContext, name: str) -> DesignNet | None:
        del context, name
        return None

    def get_pin(self, context: QueryContext, name: str) -> DesignPin | None:
        del context, name
        return None

    def get_connections(
        self, context: QueryContext, object_ref: DesignObjectRef
    ) -> Sequence[DesignConnection]:
        del context, object_ref
        return ()

    def get_fanout(
        self, context: QueryContext, net_ref: DesignObjectRef
    ) -> Sequence[DesignPin]:
        del context, net_ref
        return ()

    def get_location(
        self, context: QueryContext, instance_ref: DesignObjectRef
    ) -> DesignLocation | None:
        del context, instance_ref
        return None

    def get_instances_in_region(
        self, context: QueryContext, region: DesignRegion
    ) -> Sequence[DesignInstance]:
        del context, region
        return ()

    def query(self, request: str, context: QueryContext) -> Sequence[object]:
        """Retained as a truthful null probe for existing Phase-I callers."""

        del request, context
        return ()

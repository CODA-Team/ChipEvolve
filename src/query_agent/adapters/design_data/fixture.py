"""Small deterministic design-data adapter used for Phase III-A demos/tests."""

from __future__ import annotations

from collections.abc import Sequence

from query_agent.domain.capability import Capability
from query_agent.domain.design import (
    DesignConnection,
    DesignInstance,
    DesignLocation,
    DesignNet,
    DesignObjectKind,
    DesignObjectRef,
    DesignPin,
    DesignRegion,
    object_ref,
)
from query_agent.domain.query import QueryContext


class FixtureDesignDataProvider:
    """Provider-neutral fixture with instances, pins, and one net."""

    def __init__(self, design_id: str = "gcd") -> None:
        self.design_id = design_id
        self._u1 = object_ref(design_id, DesignObjectKind.INSTANCE, "u1")
        self._u2 = object_ref(design_id, DesignObjectKind.INSTANCE, "u2")
        self._n1 = object_ref(design_id, DesignObjectKind.NET, "n1")
        self._p1 = object_ref(design_id, DesignObjectKind.PIN, "u1/Y")
        self._p2 = object_ref(design_id, DesignObjectKind.PIN, "u2/A")
        self._instances = (
            DesignInstance(
                ref=self._u1,
                cell_type="NAND2_X1",
                location=DesignLocation(x=10.0, y=20.0, units="um"),
            ),
            DesignInstance(
                ref=self._u2,
                cell_type="BUF_X2",
                location=DesignLocation(x=40.0, y=20.0, units="um"),
            ),
        )
        self._pins = (
            DesignPin(ref=self._p1, instance=self._u1, direction="output"),
            DesignPin(ref=self._p2, instance=self._u2, direction="input"),
        )
        self._net = DesignNet(ref=self._n1, driver=self._p1)

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset(
            {
                Capability.DESIGN_OBJECT_QUERY,
                Capability.DESIGN_RELATION_QUERY,
            }
        )

    def _in_scope(self, context: QueryContext) -> bool:
        return context.design_id in (None, self.design_id)

    def get_instance(self, context: QueryContext, name: str) -> DesignInstance | None:
        if not self._in_scope(context):
            return None
        return next((item for item in self._instances if item.ref.name == name), None)

    def get_net(self, context: QueryContext, name: str) -> DesignNet | None:
        if not self._in_scope(context):
            return None
        return self._net if self._net.ref.name == name else None

    def get_pin(self, context: QueryContext, name: str) -> DesignPin | None:
        if not self._in_scope(context):
            return None
        return next((item for item in self._pins if item.ref.name == name), None)

    def get_connections(
        self, context: QueryContext, object_ref: DesignObjectRef
    ) -> Sequence[DesignConnection]:
        if not self._in_scope(context) or object_ref != self._n1:
            return ()
        if object_ref == self._n1:
            return (DesignConnection(source=self._p1, target=self._p2),)
        return ()

    def get_fanout(
        self, context: QueryContext, net_ref: DesignObjectRef
    ) -> Sequence[DesignPin]:
        if not self._in_scope(context):
            return ()
        return self._pins[1:] if net_ref == self._n1 else ()

    def get_location(
        self, context: QueryContext, instance_ref: DesignObjectRef
    ) -> DesignLocation | None:
        if not self._in_scope(context):
            return None
        instance = self.get_instance(context, instance_ref.name)
        return instance.location if instance is not None else None

    def get_instances_in_region(
        self, context: QueryContext, region: DesignRegion
    ) -> Sequence[DesignInstance]:
        if not self._in_scope(context):
            return ()
        return tuple(
            item
            for item in self._instances
            if item.location is not None
            and region.x_min <= item.location.x <= region.x_max
            and region.y_min <= item.location.y <= region.y_max
        )

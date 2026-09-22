from collections.abc import Mapping, Sequence


class FakeExecutionClient:
    def __init__(self) -> None:
        self._run = {
            "run_id": "run_02",
            "task_id": "route-task",
            "status": "succeeded",
            "created_at": "2026-09-22T12:00:00+00:00",
            "started_at": "2026-09-22T12:01:00+00:00",
            "ended_at": "2026-09-22T12:30:00+00:00",
            "terminal_reason": None,
            "stages": [
                {
                    "stage_key": "placement",
                    "ordinal": 0,
                    "plugin_id": "fixture-flow",
                    "plugin_version": "1.0.0",
                    "status": "succeeded",
                },
                {
                    "stage_key": "routing",
                    "ordinal": 1,
                    "plugin_id": "fixture-flow",
                    "plugin_version": "1.0.0",
                    "status": "succeeded",
                },
            ],
        }
        self._artifacts = [
            {
                "artifact_id": "art-route-timing",
                "kind": "timing_report",
                "store_key": "reports/route.timing.rpt",
                "sha256": "a" * 64,
                "size_bytes": 128,
                "stage_key": "routing",
                "metadata": {"format": "text"},
            },
            {
                "artifact_id": "art-place-timing",
                "kind": "timing_report",
                "store_key": "reports/place.timing.rpt",
                "sha256": "b" * 64,
                "size_bytes": 96,
                "stage_key": "placement",
                "metadata": {"format": "text"},
            },
        ]

    def run(self, run_id: str) -> Mapping[str, object]:
        assert run_id == "run_02"
        return self._run

    def metrics(
        self, run_id: str, *, complete_only: bool = False
    ) -> Sequence[Mapping[str, object]]:
        assert run_id == "run_02"
        return (
            {
                "name": "WNS",
                "value": -0.20,
                "unit": "ns",
                "parser": {"id": "timing-parser", "version": "1"},
                "artifact": {
                    "artifact_id": "art-route-timing",
                    "kind": "timing_report",
                    "sha256": "a" * 64,
                },
                "complete": True,
            },
        )

    def artifacts(
        self,
        run_id: str,
        *,
        category: str | None = None,
        format: str | None = None,
        stage: str | None = None,
    ) -> Sequence[Mapping[str, object]]:
        assert run_id == "run_02"
        del category, format
        return tuple(
            item
            for item in self._artifacts
            if stage is None or item["stage_key"] == stage
        )

    def logs(
        self, run_id: str, *, offset: int = 0, max_bytes: int | None = None
    ) -> Mapping[str, object]:
        assert run_id == "run_02"
        del offset, max_bytes
        return {"run": run_id, "content": "routing completed\nWNS=-0.20\n"}

    def artifact_excerpt(
        self, run_id: str, artifact_id: str, *, offset: int = 0, max_bytes: int = 8192
    ) -> Mapping[str, object]:
        assert run_id == "run_02"
        del offset, max_bytes
        return {
            "artifact_id": artifact_id,
            "text": "WNS: -0.20\n",
            "bytes_read": 12,
            "truncated": False,
            "sha256": "a" * 64,
        }

    def timeline(self, run_id: str) -> Sequence[Mapping[str, object]]:
        assert run_id == "run_02"
        return ({"event_type": "stage.finished", "stage": "routing"},)

    def graph(self, run_ids: Sequence[str]) -> Mapping[str, object]:
        assert tuple(run_ids) == ("run_02",)
        return {"nodes": [{"kind": "artifact", "id": "art-route-timing"}], "edges": []}

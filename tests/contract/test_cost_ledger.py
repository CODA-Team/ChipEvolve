"""Paid calls cannot bypass pending reservations or race past a global cap."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from query_agent.adapters.llm.budget import BudgetExceeded, CostLedger


def ledger(path: Path) -> CostLedger:
    path.write_text(
        json.dumps({"limits": {"jev": 1}, "settled": {"jev": 0}, "reservations": []})
    )
    return CostLedger(path)


def test_unknown_billing_keeps_reservation_and_settlement_releases_unused_amount(
    tmp_path: Path,
) -> None:
    budget = ledger(tmp_path / "cost.json")
    request = budget.reserve("jev", 0.9)
    budget.unknown(request, "timeout")
    with pytest.raises(BudgetExceeded):
        budget.reserve("jev", 0.2)
    budget.settle(request, actual_usd=0.1, usage={"input_tokens": 1}, model="jev")
    budget.reserve("jev", 0.8)
    with pytest.raises(ValueError, match="already settled"):
        budget.settle(request, actual_usd=0.1, usage={}, model="jev")


def test_concurrent_callers_obey_one_budget(tmp_path: Path) -> None:
    path = tmp_path / "cost.json"
    ledger(path)

    def reserve(_: int) -> bool:
        try:
            CostLedger(path).reserve("jev", 0.21)
            return True
        except BudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=8) as workers:
        successes = list(workers.map(reserve, range(8)))
    assert sum(successes) == 4
    rows = json.loads(path.read_text())["reservations"]
    assert len(rows) == 4 and sum(row["upper_usd"] for row in rows) < 1

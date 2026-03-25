import json
from pathlib import Path

import pytest

from commerce_agent.agent import CommerceAgent


def _router_cases() -> list[dict[str, object]]:
    with Path("tests/router_cases.json").open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.mark.parametrize("case", _router_cases())
def test_router_cases(case: dict[str, object]) -> None:
    agent = CommerceAgent()
    trace = agent.route_intent(
        str(case["prompt"]),
        has_image=bool(case["has_image"]),
    )
    assert trace.intent == case["expected_intent"]

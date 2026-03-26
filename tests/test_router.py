import json
from pathlib import Path

import pytest

from commerce_agent.agent import CommerceAgent
from commerce_agent.catalog import Catalog
from commerce_agent.router import BigModelIntentRouter, HeuristicRouter, RouterCase


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


def test_bigmodel_router_uses_llm_response(monkeypatch) -> None:
    catalog = Catalog.from_json()
    fallback = HeuristicRouter(catalog)
    router = BigModelIntentRouter(fallback, api_key="test-key", model_name="glm-4-flash")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {"intent": "chat", "rationale": "capability question"},
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    monkeypatch.setattr("commerce_agent.router.urlopen", lambda request: FakeResponse())
    trace = router.route(RouterCase(prompt="hello, what kind of search can you provide?", has_image=False))
    assert trace.intent == "chat"
    assert "bigmodel:glm-4-flash" in trace.rationale


def test_bigmodel_router_falls_back_to_heuristics_on_invalid_response(monkeypatch) -> None:
    catalog = Catalog.from_json()
    fallback = HeuristicRouter(catalog)
    router = BigModelIntentRouter(fallback, api_key="test-key", model_name="glm-4-flash")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {"intent": "unknown", "rationale": "bad"},
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    monkeypatch.setattr("commerce_agent.router.urlopen", lambda request: FakeResponse())
    trace = router.route(RouterCase(prompt="hello, what kind of search can you provide?", has_image=False))
    assert trace.intent == "chat"
    assert "heuristic fallback after llm error" in trace.rationale

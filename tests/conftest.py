import pytest


@pytest.fixture(autouse=True)
def isolate_test_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests deterministic even when a local .env contains real API keys."""
    monkeypatch.setenv("COMMERCE_AGENT_ROUTER_PROVIDER", "heuristic")
    monkeypatch.delenv("BIGMODEL_API_KEY", raising=False)
    monkeypatch.delenv("COMMERCE_AGENT_VISION_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("COMMERCE_AGENT_MOCK_VISION", "1")

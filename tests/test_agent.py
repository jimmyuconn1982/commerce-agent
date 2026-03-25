from pathlib import Path

from commerce_agent.agent import CommerceAgent
from commerce_agent.models import VisionAnalysis
from commerce_agent.vision import OpenAIVisionAnalyzer


class FakeVisionAnalyzer:
    def __init__(self, summary: str, tags: list[str]) -> None:
        self.summary = summary
        self.tags = tags

    def analyze(self, image_path: Path) -> VisionAnalysis:
        return VisionAnalysis(image_path=image_path, summary=self.summary, tags=self.tags)


def test_text_search_ranks_direct_match_first() -> None:
    agent = CommerceAgent(vision_analyzer=FakeVisionAnalyzer("unused", []))
    results = agent.text_search("keyboard", limit=2)
    assert results
    assert results[0].id == 723450000000000006


def test_image_search_matches_visual_description() -> None:
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("wood top office desk", ["desk", "office"])
    )
    analysis, results = agent.image_search("tests/fixtures/desk.png", limit=3)
    assert analysis.summary == "wood top office desk"
    assert results
    assert results[0].id == 723450000000000005


def test_multimodal_search_blends_text_and_image_intent() -> None:
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("raised keys desk", ["keyboard", "desk"])
    )
    analysis, results = agent.multimodal_search(
        text_query="office",
        image_path="tests/fixtures/keyboard.png",
        limit=3,
    )
    assert analysis is not None
    assert results
    assert results[0].id == 723450000000000006


def test_chat_returns_guided_response() -> None:
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("compact keyboard on a desk", ["keyboard", "desk"])
    )
    reply = agent.chat("I am looking for a compact keyboard for my desk", image_path="tests/fixtures/keyboard.png")
    assert "Mechanical Keyboard" not in reply
    assert "Image summary:" in reply
    assert "general conversation" in reply.lower()


def test_run_pipeline_returns_observable_trace() -> None:
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("compact keyboard on a desk", ["keyboard", "desk"])
    )
    result = agent.run_pipeline(prompt="keyboard", limit=3)
    assert result.intent == "text-search"
    assert result.trace.router.intent == "text-search"
    assert result.trace.react.initial_intent == "text-search"
    assert result.trace.react.steps
    assert result.trace.retrieval is not None
    assert result.trace.rerank is not None
    assert result.trace.retrieval.candidates
    assert result.trace.generation.selected_product_ids


def test_chat_pipeline_does_not_touch_catalog_search() -> None:
    agent = CommerceAgent(vision_analyzer=FakeVisionAnalyzer("unused", []))
    result = agent.run_pipeline(prompt="What can you do?", limit=3)
    assert result.intent == "chat"
    assert result.matches == []
    assert result.trace.retrieval is None
    assert result.trace.rerank is None
    assert result.trace.generation.selected_product_ids == []


def test_multimodal_pipeline_uses_explicit_multimodal_branch() -> None:
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("raised keys desk", ["keyboard", "desk"])
    )
    result = agent.run_pipeline(prompt="office", image_path="tests/fixtures/keyboard.png", limit=3)
    assert result.intent == "multimodal-search"
    tool_names = [step.tool_name for step in result.trace.react.steps]
    assert "multimodal_search" in tool_names


def test_mock_vision_response_allows_image_flow_without_api_key(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "green-bag.png"
    image_path.write_bytes(b"fake")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("COMMERCE_AGENT_MOCK_VISION", "1")
    monkeypatch.setenv(
        "COMMERCE_AGENT_MOCK_VISION_RESPONSE",
        "summary: compact green bag\n"
        "tags: bag, green, compact, accessory, leather",
    )

    analysis = OpenAIVisionAnalyzer().analyze(image_path)
    assert analysis.summary == "compact green bag"
    assert "green" in analysis.tags


def test_react_paths_are_exposed_as_tools() -> None:
    agent = CommerceAgent(vision_analyzer=FakeVisionAnalyzer("unused", []))
    tools = agent.get_tools()
    assert "chat_path" in tools
    assert "text_search_path" in tools
    assert "image_search_path" in tools
    assert "multimodal_search_path" in tools

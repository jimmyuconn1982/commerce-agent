from pathlib import Path

from commerce_agent.agent import CommerceAgent
from commerce_agent.chat_responder import FallbackChatResponder
from commerce_agent.models import VisionAnalysis
from commerce_agent.repository import SearchRepository
from commerce_agent.vision import BigModelVisionAnalyzer, OpenAIVisionAnalyzer


class FakeVisionAnalyzer:
    def __init__(self, summary: str, tags: list[str]) -> None:
        self.summary = summary
        self.tags = tags

    def analyze(self, image_path: Path) -> VisionAnalysis:
        return VisionAnalysis(image_path=image_path, summary=self.summary, tags=self.tags)


class FakeChatResponder:
    def __init__(self, response: str = "Scoped chat reply.") -> None:
        self.response = response
        self.calls: list[tuple[str, VisionAnalysis | None]] = []

    def generate(self, prompt: str, analysis: VisionAnalysis | None = None) -> str:
        self.calls.append((prompt, analysis))
        return self.response


class StubSearchRepository(SearchRepository):
    def __init__(self) -> None:
        self.queries: list[tuple[str, int]] = []

    def search_text(self, query: str, limit: int = 5):
        from commerce_agent.models import ParsedSearchQuery, ProductSearchHit

        self.queries.append((query, limit))
        return (
            ParsedSearchQuery(
                raw_query=query,
                normalized_query=query.lower(),
                remaining_query=query.lower(),
                category_hints=[],
                attribute_hints=[],
                min_price=None,
                max_price=None,
                sort=None,
            ),
            [
                ProductSearchHit(
                    product_id=723450000000000006,
                    title="Mechanical Keyboard",
                    short_description="Tactile mechanical keyboard with hot-swappable switches.",
                    primary_image_url="images/mechanical-keyboard.jpg",
                    price=150.0,
                    currency="USD",
                    seller_name="Home Office Co",
                    seller_rating=4.5,
                    review_count=197,
                    inventory_count=62,
                    product_url="https://example.com/products/723450000000000006",
                    category_name="electronics",
                    keyword_score=1.0,
                    semantic_score=0.5,
                    match_score=0.825,
                )
            ],
        )

    def search_image(self, image_analysis: VisionAnalysis, limit: int = 5):
        from commerce_agent.models import ProductSearchHit

        self.queries.append((f"image:{image_analysis.summary}", limit))
        return [
            ProductSearchHit(
                product_id=723450000000000005,
                title="Standing Desk",
                short_description="Electric standing desk with programmable height presets.",
                primary_image_url="images/standing-desk.jpg",
                price=416.5,
                currency="USD",
                seller_name="Home Office Co",
                seller_rating=4.5,
                review_count=189,
                inventory_count=55,
                product_url="https://example.com/products/723450000000000005",
                category_name="furniture",
                keyword_score=0.0,
                semantic_score=1.0,
                match_score=1.0,
            )
        ]

    def search_multimodal(self, query: str, image_analysis: VisionAnalysis, limit: int = 5):
        from commerce_agent.models import ParsedSearchQuery, ProductSearchHit

        self.queries.append((f"multimodal:{query}:{image_analysis.summary}", limit))
        return (
            ParsedSearchQuery(
                raw_query=query,
                normalized_query=query.lower(),
                remaining_query=query.lower(),
                category_hints=[],
                attribute_hints=[],
                min_price=None,
                max_price=None,
                sort=None,
            ),
            [
                ProductSearchHit(
                    product_id=723450000000000006,
                    title="Mechanical Keyboard",
                    short_description="Tactile mechanical keyboard with hot-swappable switches.",
                    primary_image_url="images/mechanical-keyboard.jpg",
                    price=150.0,
                    currency="USD",
                    seller_name="Home Office Co",
                    seller_rating=4.5,
                    review_count=197,
                    inventory_count=62,
                    product_url="https://example.com/products/723450000000000006",
                    category_name="electronics",
                    keyword_score=0.9,
                    semantic_score=0.8,
                    match_score=0.85,
                )
            ],
        )


def test_text_search_ranks_direct_match_first() -> None:
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("unused", []),
        search_repository=StubSearchRepository(),
    )
    results = agent.text_search("keyboard", limit=2)
    assert results
    assert results[0].id == 723450000000000006


def test_image_search_matches_visual_description() -> None:
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("wood top office desk", ["desk", "office"]),
        search_repository=StubSearchRepository(),
    )
    analysis, results = agent.image_search("tests/fixtures/desk.png", limit=3)
    assert analysis.summary == "wood top office desk"
    assert results
    assert results[0].id == 723450000000000005


def test_multimodal_search_blends_text_and_image_intent() -> None:
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("raised keys desk", ["keyboard", "desk"]),
        search_repository=StubSearchRepository(),
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
    responder = FakeChatResponder("Scoped chat reply.\nImage summary: compact keyboard on a desk")
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("compact keyboard on a desk", ["keyboard", "desk"]),
        chat_responder=responder,
    )
    reply = agent.chat("I am looking for a compact keyboard for my desk", image_path="tests/fixtures/keyboard.png")
    assert responder.calls
    assert "Image summary:" in reply


def test_run_pipeline_returns_observable_trace() -> None:
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("compact keyboard on a desk", ["keyboard", "desk"]),
        search_repository=StubSearchRepository(),
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
    responder = FakeChatResponder("Capability summary.")
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("unused", []),
        search_repository=StubSearchRepository(),
        chat_responder=responder,
    )
    result = agent.run_pipeline(prompt="What can you do?", limit=3)
    assert result.intent == "chat"
    assert result.matches == []
    assert result.trace.retrieval is None
    assert result.trace.rerank is None
    assert result.trace.generation.selected_product_ids == []


def test_chat_greeting_returns_natural_reply() -> None:
    responder = FakeChatResponder("Hello from the scoped commerce agent.")
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("unused", []),
        search_repository=StubSearchRepository(),
        chat_responder=responder,
    )
    result = agent.run_pipeline(prompt="你好啊", limit=3)
    assert result.intent == "chat"
    assert result.content == "Hello from the scoped commerce agent."
    assert result.trace.retrieval is None


def test_chat_capability_question_returns_capability_summary() -> None:
    responder = FakeChatResponder("Capability summary.")
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("unused", []),
        search_repository=StubSearchRepository(),
        chat_responder=responder,
    )
    result = agent.run_pipeline(prompt="hello，你可以提供哪些服务", limit=3)
    assert result.intent == "chat"
    assert result.content == "Capability summary."
    assert result.trace.retrieval is None


def test_english_capability_question_returns_capability_summary() -> None:
    responder = FakeChatResponder("Capability summary.")
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("unused", []),
        search_repository=StubSearchRepository(),
        chat_responder=responder,
    )
    result = agent.run_pipeline(prompt="hello, what kind of search can you provide?", limit=3)
    assert result.intent == "chat"
    assert result.content == "Capability summary."
    assert result.trace.retrieval is None


def test_general_chat_reply_stays_within_commerce_scope() -> None:
    responder = FakeChatResponder("Scoped commerce-only reply.")
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("unused", []),
        search_repository=StubSearchRepository(),
        chat_responder=responder,
    )
    result = agent.run_pipeline(prompt="Can you chat about random world history?", limit=3)
    assert result.intent == "chat"
    assert result.content == "Scoped commerce-only reply."
    assert result.trace.retrieval is None


def test_fallback_chat_responder_stays_in_scope() -> None:
    reply = FallbackChatResponder().generate("What can you do?")
    assert "commerce agent" in reply.lower()
    assert "database" in reply.lower()


def test_multimodal_pipeline_uses_explicit_multimodal_branch() -> None:
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("raised keys desk", ["keyboard", "desk"]),
        search_repository=StubSearchRepository(),
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


def test_bigmodel_vision_response_parses_summary_and_tags(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "green-bag.png"
    image_path.write_bytes(b"fake")
    monkeypatch.setenv("COMMERCE_AGENT_VISION_PROVIDER", "bigmodel")
    monkeypatch.setenv("COMMERCE_AGENT_VISION_API_KEY", "test-key")
    monkeypatch.delenv("BIGMODEL_API_KEY", raising=False)
    monkeypatch.setenv("COMMERCE_AGENT_MOCK_VISION", "0")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return (
                b'{"choices":[{"message":{"content":"summary: compact green bag\\n'
                b'tags: bag, green, compact, accessory, leather"}}]}'
            )

    monkeypatch.setattr("commerce_agent.vision.urlopen", lambda request: FakeResponse())
    analysis = BigModelVisionAnalyzer(model="glm-4.5v").analyze(image_path)
    assert analysis.summary == "compact green bag"
    assert "green" in analysis.tags


def test_react_paths_are_exposed_as_tools() -> None:
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("unused", []),
        search_repository=StubSearchRepository(),
    )
    tools = agent.get_tools()
    assert "chat_path" in tools
    assert "text_search_path" in tools
    assert "image_search_path" in tools
    assert "multimodal_search_path" in tools


def test_text_search_path_uses_search_repository() -> None:
    repository = StubSearchRepository()
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("unused", []),
        search_repository=repository,
    )

    result = agent.run_pipeline(prompt="keyboard", limit=3)
    assert repository.queries == [("keyboard", 3)]
    assert result.intent == "text-search"
    assert result.matches[0].id == 723450000000000006


def test_image_search_path_uses_search_repository() -> None:
    repository = StubSearchRepository()
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("wood top office desk", ["desk", "office"]),
        search_repository=repository,
    )

    result = agent.run_pipeline(prompt="", image_path="tests/fixtures/desk.png", limit=3)
    assert repository.queries == [("image:wood top office desk", 3)]
    assert result.intent == "image-search"
    assert result.matches[0].id == 723450000000000005


def test_multimodal_search_path_uses_search_repository() -> None:
    repository = StubSearchRepository()
    agent = CommerceAgent(
        vision_analyzer=FakeVisionAnalyzer("raised keys desk", ["keyboard", "desk"]),
        search_repository=repository,
    )

    result = agent.run_pipeline(prompt="office", image_path="tests/fixtures/keyboard.png", limit=3)
    assert repository.queries == [("multimodal:office:raised keys desk", 3)]
    assert result.intent == "multimodal-search"
    assert result.matches[0].id == 723450000000000006

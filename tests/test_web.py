from fastapi.testclient import TestClient

import commerce_agent.web as web_module
from commerce_agent.models import Product


class StubAgent:
    def __init__(self) -> None:
        self.catalog = type("CatalogStub", (), {"all": lambda self: [self._product]})()
        self.catalog._product = Product(
            id=723450000000000006,
            name="Mechanical Keyboard",
            category="electronics",
            rating=4.7,
            tags=["keyboard", "office"],
            description="Tactile mechanical keyboard with hot-swappable switches.",
            image_url="images/mechanical-keyboard.jpg",
            image_tags=["keyboard", "keys", "desk"],
            visual_description="Compact keyboard with raised keycaps.",
        )

    def chat(self, prompt: str, image_path=None) -> str:
        return f"stubbed reply for: {prompt}"

    def text_search(self, query: str, *, category=None, limit: int = 5) -> list[Product]:
        return [self.catalog._product]

    def multimodal_search(self, *, text_query="", image_path=None, category=None, limit: int = 5):
        return None, [self.catalog._product]

    def image_search(self, image_path, limit: int = 5):
        return None, [self.catalog._product]

    def classify_intent(self, prompt: str = "", has_image: bool = False) -> str:
        if has_image and prompt:
            return "multimodal-search"
        if has_image:
            return "image-search"
        if "recommend" in prompt:
            return "chat"
        return "text-search"

    def run_pipeline(self, *, prompt="", image_path=None, category=None, limit: int = 5):
        from commerce_agent.models import (
            GenerationTrace,
            PipelineResult,
            PipelineTrace,
            ReActTrace,
            RetrievalTrace,
            RerankTrace,
            RouterTrace,
            ToolCallTrace,
        )

        intent = self.classify_intent(prompt, has_image=image_path is not None)
        matches = [self.catalog._product]
        content = f"stubbed reply for: {prompt}" if intent == "chat" else "Found 1 text matches."
        router = RouterTrace(prompt=prompt, has_image=image_path is not None, intent=intent, rationale="stub")
        retrieval = RetrievalTrace(query_text=prompt, text_tokens=["keyboard"], image_tokens=[], candidates=[], limit=limit)
        rerank = RerankTrace(strategy="stub", candidates_before=[], candidates_after=[])
        generation = GenerationTrace(mode=intent, prompt=prompt, selected_product_ids=[self.catalog._product.id], response=content)
        react = ReActTrace(
            initial_intent=intent,
            final_intent=intent,
            steps=[ToolCallTrace(tool_name="stub", thought="stub", input_summary="stub", observation_summary="stub")],
        )
        trace = PipelineTrace(router=router, react=react, image_analysis=None, retrieval=retrieval, rerank=rerank, generation=generation)
        return PipelineResult(intent=intent, content=content, analysis=None, matches=matches, trace=trace)


def test_index_serves_html() -> None:
    client = TestClient(web_module.app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Commerce Agent" in response.text


def test_debug_index_serves_html() -> None:
    client = TestClient(web_module.app)
    response = client.get("/debug")
    assert response.status_code == 200
    assert "Seed Database Explorer" in response.text


def test_message_endpoint_routes_to_chat(monkeypatch) -> None:
    monkeypatch.setattr(web_module, "agent", StubAgent())
    client = TestClient(web_module.app)
    response = client.post("/api/message", data={"text": "recommend a keyboard"})
    assert response.status_code == 200
    assert response.json()["intent"] == "chat"
    assert response.json()["content"] == "stubbed reply for: recommend a keyboard"
    assert response.json()["trace"]["router"]["intent"] == "chat"


def test_message_endpoint_routes_to_text_search(monkeypatch) -> None:
    monkeypatch.setattr(web_module, "agent", StubAgent())
    client = TestClient(web_module.app)
    response = client.post("/api/message", data={"text": "keyboard", "limit": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "text-search"
    assert body["matches"][0]["id"] == 723450000000000006
    assert body["trace"]["router"]["intent"] == "text-search"


def test_multimodal_text_only_returns_matches(monkeypatch) -> None:
    monkeypatch.setattr(web_module, "agent", StubAgent())
    client = TestClient(web_module.app)
    response = client.post("/api/message", data={"text": "keyboard", "limit": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["analysis"] is None
    assert body["matches"][0]["id"] == 723450000000000006


def test_debug_seed_summary_returns_counts() -> None:
    client = TestClient(web_module.app)
    response = client.get("/api/debug/seed-summary")
    assert response.status_code == 200
    body = response.json()
    assert "products" in body
    assert "text_embeddings" in body


def test_debug_products_returns_joined_rows() -> None:
    client = TestClient(web_module.app)
    response = client.get("/api/debug/products?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert body["products"]
    first = body["products"][0]
    assert "title" in first
    assert "search_text" in first
    assert "image_tags" in first
    assert "search_terms" in first
    assert "cooking_uses" in first
    assert "audience_terms" in first


def test_debug_product_detail_returns_joined_detail() -> None:
    client = TestClient(web_module.app)
    list_response = client.get("/api/debug/products?limit=1")
    product_id = list_response.json()["products"][0]["product_id"]
    response = client.get(f"/api/debug/products/{product_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["product"]["product_id"] == product_id
    assert "media" in body
    assert "embeddings" in body
    assert "search_terms" in body["product"]
    assert "cooking_uses" in body["product"]
    assert "audience_terms" in body["product"]


def test_debug_run_uses_same_pipeline_shape(monkeypatch) -> None:
    monkeypatch.setattr(web_module, "agent", StubAgent())
    client = TestClient(web_module.app)
    response = client.post("/api/debug/run", data={"text": "keyboard", "limit": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "text-search"
    assert body["trace"]["router"]["intent"] == "text-search"

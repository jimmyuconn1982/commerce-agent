from __future__ import annotations

"""FastAPI entrypoint for the chat-style frontend.

Inputs:
- multipart form requests with text, local images, or image URLs

Outputs:
- routed chat/search responses shaped for the web client

Role:
- bridge browser uploads into the backend pipeline
- keep transport concerns outside the agent core

Upgrade path:
- add debug endpoints for trace inspection
- split public and developer APIs as backend observability grows
"""

import json
import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

import httpx
import psycopg
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .agent import CommerceAgent
from .api_models import DebugProductResponse, RoutedMessageResponse
from .config import get_settings
from .repository import PostgresSearchRepository
from .seed_data import DEFAULT_DATABASE_URL

STATIC_DIR = Path(__file__).resolve().parents[2] / "web"

app = FastAPI(title="Commerce Agent Web")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.middleware("http")
async def disable_browser_caching(request: Request, call_next) -> Response:
    """Force fresh frontend assets while the UI is under active development."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

agent = CommerceAgent(search_repository=PostgresSearchRepository())


@app.get("/")
def index() -> FileResponse:
    """Serve the single-page frontend shell."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/debug")
def debug_index() -> FileResponse:
    """Serve the product-debug GUI for inspecting database-backed seed data."""
    return FileResponse(STATIC_DIR / "debug.html")


@app.get("/api/catalog")
def get_catalog() -> dict[str, object]:
    """Return the current product catalog for frontend bootstrap and debug."""
    return {"products": [asdict(product) for product in agent.catalog.all()]}


@app.get("/api/debug/seed-summary")
def get_seed_summary() -> dict[str, int]:
    """Return compact row counts for the current local debug database."""
    database_url = getattr(agent.search_repository, "database_url", None) or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM categories) AS categories,
                    (SELECT COUNT(*) FROM products) AS products,
                    (SELECT COUNT(*) FROM product_media) AS product_media,
                    (SELECT COUNT(*) FROM product_search_documents) AS search_docs,
                    (SELECT COUNT(*) FROM product_embeddings WHERE embedding_type = 'text') AS text_embeddings,
                    (SELECT COUNT(*) FROM product_embeddings WHERE embedding_type = 'image') AS image_embeddings
                """
            )
            row = cur.fetchone()
    return {
        "categories": row[0],
        "products": row[1],
        "product_media": row[2],
        "search_docs": row[3],
        "text_embeddings": row[4],
        "image_embeddings": row[5],
    }


@app.get("/api/debug/products")
def get_debug_products(limit: int = 100) -> dict[str, object]:
    """Return joined product debug rows for the backend seed explorer."""
    limit = max(1, min(limit, 500))
    database_url = getattr(agent.search_repository, "database_url", None) or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id,
                    p.sku,
                    p.title,
                    c.name AS category_name,
                    p.brand,
                    p.short_description,
                    p.long_description,
                    pm.url AS primary_image_url,
                    pm.thumbnail_url,
                    pm.alt_text AS image_alt_text,
                    s.name AS seller_name,
                    COALESCE(s.rating, 0) AS seller_rating,
                    po.price,
                    po.currency,
                    po.inventory_count,
                    COALESCE(prs.review_count, 0) AS review_count,
                    COALESCE(prs.average_rating, 0) AS average_rating,
                    po.product_url,
                    psd.search_text,
                    p.attributes_jsonb,
                    EXISTS (
                        SELECT 1
                        FROM product_embeddings pe
                        WHERE pe.product_id = p.id
                          AND pe.embedding_type = 'text'
                    ) AS has_text_embedding,
                    EXISTS (
                        SELECT 1
                        FROM product_embeddings pe
                        WHERE pe.product_id = p.id
                          AND pe.embedding_type = 'image'
                    ) AS has_image_embedding
                FROM products p
                JOIN categories c ON c.id = p.category_id
                LEFT JOIN product_search_documents psd ON psd.product_id = p.id
                LEFT JOIN LATERAL (
                    SELECT pm.url, pm.thumbnail_url, pm.alt_text
                    FROM product_media pm
                    WHERE pm.product_id = p.id AND pm.is_primary = TRUE
                    ORDER BY pm.sort_order ASC, pm.id ASC
                    LIMIT 1
                ) pm ON TRUE
                LEFT JOIN LATERAL (
                    SELECT po.price, po.currency, po.inventory_count, po.product_url, po.seller_id
                    FROM product_offers po
                    WHERE po.product_id = p.id AND po.is_active = TRUE
                    ORDER BY po.price ASC, po.id ASC
                    LIMIT 1
                ) po ON TRUE
                LEFT JOIN sellers s ON s.id = po.seller_id
                LEFT JOIN product_review_stats prs ON prs.product_id = p.id
                ORDER BY p.id
                LIMIT %(limit)s
                """,
                {"limit": limit},
            )
            rows = cur.fetchall()

    products: list[dict[str, object]] = []
    for row in rows:
        attributes = row[19] or {}
        text_tags = attributes.get("tags", []) if isinstance(attributes, dict) else []
        image_tags = attributes.get("image_tags", []) if isinstance(attributes, dict) else []
        payload = DebugProductResponse(
            product_id=row[0],
            sku=row[1],
            title=row[2],
            category_name=row[3],
            brand=row[4],
            short_description=row[5],
            long_description=row[6],
            primary_image_url=row[7],
            thumbnail_url=row[8],
            image_alt_text=row[9],
            seller_name=row[10],
            seller_rating=float(row[11]) if row[11] is not None else None,
            price=float(row[12]) if row[12] is not None else None,
            currency=row[13],
            inventory_count=row[14],
            review_count=row[15],
            average_rating=float(row[16]) if row[16] is not None else None,
            product_url=row[17],
            search_text=row[18],
            attributes=attributes if isinstance(attributes, dict) else {},
            text_tags=list(text_tags) if isinstance(text_tags, list) else [],
            image_tags=list(image_tags) if isinstance(image_tags, list) else [],
            has_text_embedding=bool(row[20]),
            has_image_embedding=bool(row[21]),
        ).model_dump()
        products.append(payload)
    return {"products": products, "limit": limit}

@app.post("/api/message")
async def message(
    text: str = Form(""),
    file: UploadFile | None = File(None),
    image_url: str = Form(""),
    limit: int = Form(5),
) -> dict[str, object]:
    """Handle one chat-style request and return the routed backend result."""
    # The web API exposes a single unified message endpoint. Intent routing
    # happens inside the backend pipeline, not in the transport layer.
    if not text and file is None and not image_url.strip():
        raise HTTPException(status_code=400, detail="text or file is required")

    temp_path: Path | None = None
    try:
        if file is not None or image_url.strip():
            temp_path = await _resolve_image_input(file, image_url)
        result = agent.run_pipeline(
            prompt=text or "Find something like this image.",
            image_path=temp_path,
            limit=limit,
        )
        return RoutedMessageResponse(
            intent=result.intent,
            content=result.content,
            analysis=asdict(result.analysis) if result.analysis else None,
            matches=[asdict(product) for product in result.matches],
            trace=asdict(result.trace),
            limit=limit,
        ).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _save_upload(file: UploadFile) -> Path:
    """Persist one uploaded file into a temporary local path."""
    suffix = Path(file.filename or "upload.bin").suffix or ".bin"
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = Path(handle.name)
    with handle:
        shutil.copyfileobj(file.file, handle)
    return temp_path


async def _resolve_image_input(file: UploadFile | None, image_url: str) -> Path | None:
    """Resolve either an uploaded image or a remote image URL into a local path."""
    if file is not None and file.filename:
        return _save_upload(file)
    if image_url.strip():
        return await _download_image(image_url.strip())
    raise HTTPException(status_code=400, detail="image file or image_url is required")


async def _download_image(image_url: str) -> Path:
    """Download a remote image URL into a temporary local file."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.get(image_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"failed to fetch image URL: {image_url}") from exc

    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="image_url did not return an image")

    suffix = _suffix_from_content_type(content_type)
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = Path(handle.name)
    with handle:
        handle.write(response.content)
    return temp_path


def _suffix_from_content_type(content_type: str) -> str:
    """Infer a reasonable file suffix from the HTTP content type."""
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    if "gif" in content_type:
        return ".gif"
    return ".jpg"


def main() -> None:
    """Start the local FastAPI server with environment-based host and port."""
    settings = get_settings().web
    uvicorn.run("commerce_agent.web:app", host=settings.host, port=settings.port, reload=False)

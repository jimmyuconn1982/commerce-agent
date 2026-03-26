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

import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .agent import CommerceAgent
from .api_models import RoutedMessageResponse
from .config import get_settings
from .repository import PostgresSearchRepository

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


@app.get("/api/catalog")
def get_catalog() -> dict[str, object]:
    """Return the current product catalog for frontend bootstrap and debug."""
    return {"products": [asdict(product) for product in agent.catalog.all()]}

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

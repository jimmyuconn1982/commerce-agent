from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agent import CommerceAgent
from .api_models import RoutedMessageResponse

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

agent = CommerceAgent()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/catalog")
def get_catalog() -> dict[str, object]:
    return {"products": [asdict(product) for product in agent.catalog.all()]}

@app.post("/api/message")
async def message(
    text: str = Form(""),
    file: UploadFile | None = File(None),
    image_url: str = Form(""),
    limit: int = Form(5),
) -> dict[str, object]:
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
            limit=limit,
        ).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _save_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "upload.bin").suffix or ".bin"
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = Path(handle.name)
    with handle:
        shutil.copyfileobj(file.file, handle)
    return temp_path


async def _resolve_image_input(file: UploadFile | None, image_url: str) -> Path | None:
    if file is not None and file.filename:
        return _save_upload(file)
    if image_url.strip():
        return await _download_image(image_url.strip())
    raise HTTPException(status_code=400, detail="image file or image_url is required")


async def _download_image(image_url: str) -> Path:
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
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    if "gif" in content_type:
        return ".gif"
    return ".jpg"


def main() -> None:
    host = os.getenv("COMMERCE_AGENT_HOST", "127.0.0.1")
    port = int(os.getenv("COMMERCE_AGENT_PORT", "8000"))
    uvicorn.run("commerce_agent.web:app", host=host, port=port, reload=False)

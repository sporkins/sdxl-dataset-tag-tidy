from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse, Response
from PIL import Image

from app.deps import get_config_service, get_dataset_manager
from app.services.config_service import ConfigService
from app.services.dataset_manager import DatasetManager

router = APIRouter()


def _validate_image_path(image_path: Path, dataset_path: Path) -> None:
    resolved = image_path.resolve()
    dataset_resolved = dataset_path.resolve()
    try:
        resolved.relative_to(dataset_resolved)
    except ValueError:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": {"code": "FORBIDDEN", "message": "Invalid image path."}})


@router.get("/img/full/{image_id}")
def full_image(image_id: str, manager: DatasetManager = Depends(get_dataset_manager)):
    manager.require_loaded()
    image_path = manager.get_image_absolute_path(image_id)
    dataset_path = manager.dataset_path  # type: ignore[assignment]
    _validate_image_path(image_path, dataset_path)
    return FileResponse(str(image_path))


@router.get("/img/thumb/{image_id}")
def thumbnail(
    image_id: str,
    w: Optional[int] = Query(256, gt=0, le=2048),
    manager: DatasetManager = Depends(get_dataset_manager),
    config: ConfigService = Depends(get_config_service),
):
    manager.require_loaded()
    image_path = manager.get_image_absolute_path(image_id)
    dataset_path = manager.dataset_path  # type: ignore[assignment]
    _validate_image_path(image_path, dataset_path)
    width = w or 256

    cache_settings = config.thumbnail_cache_settings
    cache_file: Optional[Path] = None
    if cache_settings.enabled and cache_settings.mode == "disk":
        cache_dir = dataset_path / cache_settings.dir_name
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{image_id}_w{width}{image_path.suffix}"
        if cache_file.exists():
            return FileResponse(str(cache_file))

    with Image.open(image_path) as img:
        img_copy = img.copy()
        img_copy.thumbnail((width, width))
        buffer = io.BytesIO()
        img_copy.save(buffer, format=img_copy.format or "PNG")
        content = buffer.getvalue()

    if cache_file:
        cache_file.write_bytes(content)

    return Response(content, media_type=f"image/{(image_path.suffix or '.png').lstrip('.')}")

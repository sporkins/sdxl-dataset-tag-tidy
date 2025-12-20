from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.deps import get_config_service, get_dataset_manager, get_lm_studio_service
from app.services.config_service import ConfigService
from app.services.dataset_manager import DatasetManager
from app.services.lmstudio_service import (
    LmStudioError,
    LmStudioInvalidResponseError,
    LmStudioService,
    LmStudioTimeoutError,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


async def _coerce_payload(request: Request) -> Dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        return await request.json()
    form = await request.form()
    data: Dict[str, Any] = {}
    for key, value in form.multi_items():
        if "[" in key and key.endswith("]"):
            base, inner = key.split("[", 1)
            inner = inner.rstrip("]")
            bucket = data.setdefault(base, {})
            bucket[inner] = value
        else:
            if key in data:
                existing = data[key]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    data[key] = [existing, value]
            else:
                data[key] = value
    return data


@router.get("/browse")
def browse(rel: str | None = None, manager: DatasetManager = Depends(get_dataset_manager)):
    return manager.browse(rel)


@router.post("/config/dataset-root")
async def set_dataset_root(
    request: Request,
    manager: DatasetManager = Depends(get_dataset_manager),
    config: ConfigService = Depends(get_config_service),
):
    payload = await _coerce_payload(request)
    root_value = (payload.get("dataset_root") or "").strip()
    if not root_value:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": "INVALID_ROOT", "message": "Dataset root is required."}},
        )
    root_path = Path(root_value)
    if not root_path.exists() or not root_path.is_dir():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": "INVALID_ROOT", "message": "Dataset root must be an existing folder."}},
        )
    config.save_dataset_root(root_path)
    manager.refresh_dataset_root()
    return {"ok": True, "dataset_root": str(root_path)}


@router.post("/dataset/load")
async def load_dataset(request: Request, manager: DatasetManager = Depends(get_dataset_manager)):
    payload = await _coerce_payload(request)
    rel = payload.get("rel") or ""
    summary = manager.load_dataset(rel)
    return summary


@router.get("/dataset/summary")
def dataset_summary(manager: DatasetManager = Depends(get_dataset_manager)):
    summary = manager.get_dataset_summary()
    return asdict(summary)


@router.get("/image/{image_id}/tags")
def image_tags(image_id: str, manager: DatasetManager = Depends(get_dataset_manager)):
    return manager.get_image_tags(image_id)


@router.get("/image/{image_id}/hint-options")
def hint_options(
    request: Request,
    image_id: str,
    category: str,
    hint_type: str = "missing",
    manager: DatasetManager = Depends(get_dataset_manager),
):
    manager.get_image(image_id)
    from app.services.tag_service import TagService

    options = TagService.hint_options(category)
    return templates.TemplateResponse(
        "fragments/hint_options.html",
        {
            "request": request,
            "image_id": image_id,
            "category": category,
            "hint_type": hint_type,
            "options": options.get("options", []),
            "allows_freeform": options.get("allows_freeform", False),
        },
    )


@router.post("/ops/bulk")
async def bulk_op(request: Request, manager: DatasetManager = Depends(get_dataset_manager)):
    payload = await _coerce_payload(request)
    scope = payload.get("scope") or {}
    op = payload.get("op") or {}
    # Map filter fields when originating from the filters form
    if "filter" not in scope:
        scope["filter"] = {
            "filename_contains": payload.get("filename_contains") or None,
            "has_tag": payload.get("has_tag") or None,
            "has_undesired": payload.get("has_undesired") in ("true", True),
            "has_missing_required": payload.get("has_missing_required") in ("true", True),
        }
    if "selected_image_ids" not in scope and payload.get("selected_image_ids"):
        ids = payload.get("selected_image_ids")
        if not isinstance(ids, list):
            ids = [ids]
        scope["selected_image_ids"] = ids
    result = manager.stage_bulk_edit(scope, op)
    return result


@router.post("/image/{image_id}/ops")
async def image_op(image_id: str, request: Request, manager: DatasetManager = Depends(get_dataset_manager)):
    payload = await _coerce_payload(request)
    return manager.stage_image_edit(image_id, payload)


@router.get("/changes")
def changes(manager: DatasetManager = Depends(get_dataset_manager)):
    summary = manager.get_changes()
    return asdict(summary)


@router.post("/changes/apply")
async def apply_changes(manager: DatasetManager = Depends(get_dataset_manager)):
    return manager.apply_changes()


@router.post("/changes/discard")
async def discard_changes(manager: DatasetManager = Depends(get_dataset_manager)):
    return manager.discard_changes()


@router.get("/undesired")
def undesired(config: ConfigService = Depends(get_config_service)):
    return {"tags": config.load_undesired_tags()}


@router.post("/undesired/add")
async def undesired_add(request: Request, config: ConfigService = Depends(get_config_service)):
    payload = await _coerce_payload(request)
    tag = (payload.get("tag") or "").strip()
    tags = config.load_undesired_tags()
    if tag and tag not in tags:
        tags.append(tag)
        config.save_undesired_tags(tags)
    return {"ok": True}


@router.post("/undesired/remove")
async def undesired_remove(request: Request, config: ConfigService = Depends(get_config_service)):
    payload = await _coerce_payload(request)
    tag = (payload.get("tag") or "").strip()
    tags = [t for t in config.load_undesired_tags() if t != tag]
    config.save_undesired_tags(tags)
    return {"ok": True}


@router.post("/image/{image_id}/analyze")
async def analyze_image(
    image_id: str,
    manager: DatasetManager = Depends(get_dataset_manager),
    config: ConfigService = Depends(get_config_service),
    lm_service: LmStudioService = Depends(get_lm_studio_service),
):
    try:
        manager.require_loaded()
    except HTTPException as exc:
        if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=exc.detail)
        raise

    try:
        image = manager.get_image(image_id)
    except HTTPException:
        raise

    exclusions = config.load_undesired_tags()

    try:
        suggested_tags = await lm_service.analyze_image(image.abs_path, image.tags_current, exclusions=exclusions)
    except LmStudioTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "LM_TIMEOUT", "message": str(exc)}},
        ) from exc
    except LmStudioInvalidResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "LM_INVALID", "message": str(exc)}},
        ) from exc
    except LmStudioError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "LM_ERROR", "message": str(exc)}},
        ) from exc

    current_lower = [tag.lower() for tag in image.tags_current]
    suggested_set = set(suggested_tags)
    added = [tag for tag in suggested_tags if tag not in current_lower]
    removed = [tag for tag in image.tags_current if tag.lower() not in suggested_set]

    return {
        "image_id": image_id,
        "current_tags": image.tags_current,
        "suggested_tags": suggested_tags,
        "diff": {"added": added, "removed": removed},
    }

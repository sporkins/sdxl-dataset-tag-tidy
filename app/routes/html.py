from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.deps import get_config_service, get_dataset_manager
from app.models import FilterCriteria
from app.services.config_service import ConfigService
from app.services.dataset_manager import DatasetManager

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/")
def dataset_picker(request: Request, rel: str | None = None, manager: DatasetManager = Depends(get_dataset_manager)):
    error_message = None
    try:
        browse_data = manager.browse(rel or "")
    except HTTPException as exc:  # type: ignore[catching-any]
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        error_message = detail.get("error", {}).get("message", "Unable to browse dataset root.")
        browse_data = {"current": {"rel": ""}, "parent": {"rel": ""}, "dirs": [], "summary": {"eligible_image_count_recursive": 0}}
    context = {
        "request": request,
        "browse": browse_data,
        "dataset_rel": manager.get_dataset_rel(),
        "error_message": error_message,
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("fragments/picker_browser.html", context)
    return templates.TemplateResponse("picker.html", context)


@router.get("/dataset")
def dataset_view(
    request: Request,
    filename_contains: Optional[str] = None,
    has_tag: Optional[str] = None,
    has_undesired: Optional[str] = None,
    has_missing_required: Optional[str] = None,
    manager: DatasetManager = Depends(get_dataset_manager),
    config: ConfigService = Depends(get_config_service),
):
    try:
        manager.require_loaded()
    except Exception:
        return RedirectResponse("/", status_code=302)

    filters = FilterCriteria.from_dict(
        {
            "filename_contains": filename_contains,
            "has_tag": has_tag,
            "has_undesired": has_undesired,
            "has_missing_required": has_missing_required,
        }
    )
    summary = manager.get_dataset_summary(filters)
    changes = asdict(manager.get_changes())
    context = {
        "request": request,
        "summary": summary,
        "changes": changes,
        "filters": filters,
        "undesired_tags": config.load_undesired_tags(),
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("fragments/dataset_content.html", context)
    return templates.TemplateResponse("dataset.html", context)


@router.get("/image/{image_id}")
def image_detail(request: Request, image_id: str, manager: DatasetManager = Depends(get_dataset_manager), config: ConfigService = Depends(get_config_service)):
    try:
        manager.require_loaded()
    except Exception:
        return RedirectResponse("/", status_code=302)
    image = manager.get_image(image_id)
    from app.services.tag_service import TagService

    hints_map = TagService.compute_hints(image.tags_current)
    undesired_lookup = {tag.lower() for tag in config.load_undesired_tags()}
    return templates.TemplateResponse(
        "image_detail.html",
        {
            "request": request,
            "image": image,
            "hints": hints_map,
            "undesired_tags": undesired_lookup,
        },
    )


@router.get("/settings/undesired")
def undesired_settings(request: Request, config: ConfigService = Depends(get_config_service)):
    tags = config.load_undesired_tags()
    return templates.TemplateResponse(
        "undesired.html",
        {"request": request, "tags": tags},
    )

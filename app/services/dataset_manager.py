from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException, status

from app.models import (
    ChangeEntry,
    ChangeSummary,
    DatasetSummary,
    FilterCriteria,
    IMAGE_EXTENSIONS,
    ImageData,
)
from app.services.config_service import ConfigService
from app.services.tag_service import TagService


class DatasetManager:
    def __init__(self, config_service: ConfigService):
        self.config_service = config_service
        self.dataset_root: Optional[Path] = None
        self.dataset_rel: Optional[str] = None
        self.dataset_path: Optional[Path] = None
        self.images: Dict[str, ImageData] = {}
        self.refresh_dataset_root()

    def _error(self, status_code: int, code: str, message: str) -> HTTPException:
        return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})

    def _normalize_rel(self, rel: Optional[str]) -> str:
        from pathlib import PurePath

        if rel in (None, ""):
            return ""
        pure = PurePath(rel)
        if pure.is_absolute() or pure.drive:
            raise self._error(status.HTTP_400_BAD_REQUEST, "INVALID_PATH", "Absolute paths are not allowed.")
        normalized = Path(*pure.parts)
        if any(part == ".." for part in normalized.parts):
            raise self._error(status.HTTP_400_BAD_REQUEST, "INVALID_PATH", "Path traversal is not allowed.")
        return normalized.as_posix()

    def refresh_dataset_root(self) -> None:
        configured = self.config_service.get_dataset_root()
        new_root = configured.resolve() if configured else None
        if new_root != self.dataset_root:
            self.dataset_root = new_root
            self.dataset_rel = None
            self.dataset_path = None
            self.images = {}

    def _require_dataset_root(self) -> Path:
        if not self.dataset_root:
            raise self._error(status.HTTP_503_SERVICE_UNAVAILABLE, "NO_ROOT", "Dataset root is not configured.")
        return self.dataset_root

    def _resolve_rel(self, rel: Optional[str]) -> Tuple[str, Path]:
        normalized = self._normalize_rel(rel)
        root = self._require_dataset_root()
        target = (root / normalized).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            raise self._error(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Path escapes dataset root.")
        return normalized, target

    def browse(self, rel: Optional[str]) -> Dict[str, object]:
        self.refresh_dataset_root()
        normalized, target = self._resolve_rel(rel)
        if not target.exists():
            raise self._error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Folder does not exist.")
        if not target.is_dir():
            raise self._error(status.HTTP_400_BAD_REQUEST, "INVALID_PATH", "Target is not a directory.")

        dirs = []
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            if child.is_dir():
                dirs.append({"name": child.name})

        parent_path = Path(normalized).parent.as_posix() if normalized else ""
        parent_rel = "" if parent_path in ("", ".") else parent_path
        return {
            "current": {"rel": normalized},
            "parent": {"rel": parent_rel},
            "dirs": dirs,
            "summary": {"eligible_image_count_recursive": self._count_images_recursive(target)},
        }

    def _count_images_recursive(self, target: Path) -> int:
        count = 0
        for path in target.rglob("*"):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                count += 1
        return count

    def load_dataset(self, rel: str) -> Dict[str, object]:
        self.refresh_dataset_root()
        normalized, target = self._resolve_rel(rel)
        if not target.exists():
            raise self._error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Folder does not exist.")
        if not target.is_dir():
            raise self._error(status.HTTP_400_BAD_REQUEST, "INVALID_PATH", "Target is not a directory.")

        image_files = sorted(
            [p for p in target.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS],
            key=lambda p: p.as_posix().lower(),
        )
        if not image_files:
            raise self._error(status.HTTP_422_UNPROCESSABLE_ENTITY, "NO_IMAGES", "No images found in folder.")
        if len(image_files) > 200:
            raise self._error(status.HTTP_422_UNPROCESSABLE_ENTITY, "TOO_MANY", "Dataset exceeds 200 image limit.")

        self.dataset_rel = normalized
        self.dataset_path = target
        self.images = {}
        for img_path in image_files:
            rel_path = img_path.relative_to(target).as_posix()
            image_id = hashlib.sha1(rel_path.encode("utf-8")).hexdigest()
            tags_raw = self._read_tags(img_path)
            tags = TagService.normalize_on_load(tags_raw)
            self.images[image_id] = ImageData(
                image_id=image_id,
                rel_path=rel_path,
                abs_path=img_path,
                tags_original=tags,
                tags_current=list(tags),
            )

        unique_tags = set()
        for image in self.images.values():
            unique_tags.update(image.tags_current)
        return {
            "dataset_rel": self.dataset_rel,
            "image_count": len(self.images),
            "tag_total_unique": len(unique_tags),
            "warnings": [],
        }

    def _read_tags(self, image_path: Path) -> str:
        tag_path = image_path.with_suffix(".txt")
        if not tag_path.exists():
            return ""
        return tag_path.read_text(encoding="utf-8", errors="ignore")

    def get_dataset_summary(self, filters: Optional[FilterCriteria] = None) -> DatasetSummary:
        if not self.dataset_path or self.dataset_rel is None:
            raise self._error(status.HTTP_404_NOT_FOUND, "NO_DATASET", "No dataset loaded.")
        criteria = filters or FilterCriteria()
        undesired_tags = set(tag.lower() for tag in self.config_service.load_undesired_tags())
        images_payload = []
        tag_counts: Dict[str, int] = {}

        for image in self._filtered_images(criteria):
            for tag in image.tags_current:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            hints = TagService.compute_hints(image.tags_current)
            images_payload.append(
                {
                    "image_id": image.image_id,
                    "filename": Path(image.rel_path).name,
                    "rel_path": image.rel_path,
                    "tag_count": len(image.tags_current),
                    "has_undesired": bool(undesired_tags.intersection(set(t.lower() for t in image.tags_current))),
                    "hints": hints,
                }
            )

        tags_payload = [
            {"tag": tag, "count": count, "is_undesired": tag.lower() in undesired_tags}
            for tag, count in sorted(tag_counts.items(), key=lambda item: item[0])
        ]

        return DatasetSummary(
            dataset_rel=self.dataset_rel,
            image_count=len(self.images),
            tags=tags_payload,
            images=images_payload,
        )

    def _filtered_images(self, criteria: FilterCriteria) -> Iterable[ImageData]:
        undesired_set = set(tag.lower() for tag in self.config_service.load_undesired_tags())
        for image in self.images.values():
            if criteria.filename_contains:
                if criteria.filename_contains.lower() not in image.rel_path.lower():
                    continue
            if criteria.has_tag:
                if criteria.has_tag not in image.tags_current:
                    continue
            if criteria.has_undesired is not None:
                has_flag = bool(undesired_set.intersection({t.lower() for t in image.tags_current}))
                if has_flag != bool(criteria.has_undesired):
                    continue
            if criteria.has_missing_required is not None:
                hints = TagService.compute_hints(image.tags_current)
                missing = bool(hints.get("missing_required"))
                if missing != bool(criteria.has_missing_required):
                    continue
            yield image

    def get_image_tags(self, image_id: str) -> Dict[str, object]:
        image = self.images.get(image_id)
        if not image:
            raise self._error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Image not found.")
        return {"image_id": image_id, "tags": image.tags_current, "is_dirty": image.is_dirty()}

    def get_neighbor_ids(self, image_id: str) -> Dict[str, Optional[str]]:
        if image_id not in self.images:
            raise self._error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Image not found.")
        image_ids = list(self.images.keys())
        index = image_ids.index(image_id)
        previous_id = image_ids[index - 1] if index > 0 else None
        next_id = image_ids[index + 1] if index < len(image_ids) - 1 else None
        return {"previous": previous_id, "next": next_id}

    def stage_image_edit(self, image_id: str, op: Dict[str, object]) -> Dict[str, object]:
        image = self.images.get(image_id)
        if not image:
            raise self._error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Image not found.")

        op_type = op.get("type")
        if op_type == "add":
            tag = (op.get("tag") or "").strip()
            if tag and tag not in image.tags_current:
                image.tags_current.append(tag)
        elif op_type == "delete":
            tag = (op.get("tag") or "").strip()
            image.tags_current = [t for t in image.tags_current if t != tag]
        elif op_type == "reorder":
            tags = op.get("tags") or []
            if not isinstance(tags, list):
                raise self._error(status.HTTP_400_BAD_REQUEST, "INVALID_OP", "Tags must be a list.")
            normalized_new = [str(t).strip() for t in tags if str(t).strip()]
            if not self._tags_match(normalized_new, image.tags_current):
                raise self._error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_REORDER", "Tags must match current set.")
            image.tags_current = normalized_new
        else:
            raise self._error(status.HTTP_400_BAD_REQUEST, "INVALID_OP", "Unsupported operation.")

        return {"image_id": image_id, "is_dirty": image.is_dirty()}

    def _tags_match(self, proposed: List[str], current: List[str]) -> bool:
        if len(proposed) != len(current):
            return False
        from collections import Counter

        return Counter(proposed) == Counter(current)

    def stage_bulk_edit(self, scope: Dict[str, object], op: Dict[str, object]) -> Dict[str, object]:
        mode = scope.get("mode")
        selected_ids = scope.get("selected_image_ids") or []
        filter_criteria = FilterCriteria.from_dict(scope.get("filter") or {})
        if mode == "filtered":
            criteria_to_use = filter_criteria
        elif mode == "selected":
            criteria_to_use = FilterCriteria()
        else:
            criteria_to_use = FilterCriteria()

        images = list(self._bulk_target_images(mode, selected_ids, criteria_to_use))
        summary = {"added": 0, "removed": 0, "replaced": 0}

        for image in images:
            op_type = op.get("type")
            if op_type == "add":
                tag = (op.get("tag") or "").strip()
                if tag and tag not in image.tags_current:
                    image.tags_current.append(tag)
                    summary["added"] += 1
            elif op_type == "delete":
                tag = (op.get("tag") or "").strip()
                before = len(image.tags_current)
                image.tags_current = [t for t in image.tags_current if t != tag]
                if len(image.tags_current) != before:
                    summary["removed"] += 1
            elif op_type == "replace":
                old_tag = (op.get("old_tag") or "").strip()
                new_tag = (op.get("new_tag") or "").strip()
                if not old_tag or not new_tag:
                    continue
                if old_tag in image.tags_current:
                    image.tags_current = [new_tag if t == old_tag else t for t in image.tags_current]
                    summary["replaced"] += 1
            else:
                raise self._error(status.HTTP_400_BAD_REQUEST, "INVALID_OP", "Unsupported bulk operation.")

        return {"affected_images": len(images), "summary": summary}

    def _bulk_target_images(
        self, mode: Optional[str], selected_ids: List[str], criteria: FilterCriteria
    ) -> Iterable[ImageData]:
        if mode == "selected":
            for image_id in selected_ids:
                image = self.images.get(image_id)
                if image:
                    yield image
            return
        if mode == "filtered":
            for image in self._filtered_images(criteria):
                yield image
            return
        for image in self.images.values():
            yield image

    def get_changes(self) -> ChangeSummary:
        changes: List[ChangeEntry] = []
        for image in self.images.values():
            added = image.added_tags()
            removed = image.removed_tags()
            reordered = image.reordered()
            if added or removed or reordered:
                changes.append(ChangeEntry(image_id=image.image_id, added=added, removed=removed, reordered=reordered))
        return ChangeSummary(dirty_images=len(changes), changes=changes)

    def apply_changes(self) -> Dict[str, object]:
        if not self.dataset_path:
            raise self._error(status.HTTP_404_NOT_FOUND, "NO_DATASET", "No dataset loaded.")
        written = 0
        for image in self.images.values():
            if not image.is_dirty():
                continue
            tag_path = image.abs_path.with_suffix(".txt")
            content = TagService.normalize_on_save(image.tags_current)
            tag_path.parent.mkdir(parents=True, exist_ok=True)
            tag_path.write_text(content, encoding="utf-8")
            image.tags_original = list(image.tags_current)
            written += 1
        return {"applied": True, "written_files": written}

    def discard_changes(self) -> Dict[str, object]:
        for image in self.images.values():
            image.tags_current = list(image.tags_original)
        return {"discarded": True}

    def get_image(self, image_id: str) -> ImageData:
        image = self.images.get(image_id)
        if not image:
            raise self._error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Image not found.")
        return image

    def require_loaded(self) -> None:
        if not self.dataset_path:
            raise self._error(status.HTTP_404_NOT_FOUND, "NO_DATASET", "No dataset loaded.")

    def get_image_absolute_path(self, image_id: str) -> Path:
        self.require_loaded()
        image = self.get_image(image_id)
        return image.abs_path

    def get_dataset_root(self) -> Optional[Path]:
        return self.dataset_root

    def get_dataset_rel(self) -> Optional[str]:
        return self.dataset_rel

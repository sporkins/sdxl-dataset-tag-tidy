from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class ImageData:
    image_id: str
    rel_path: str
    abs_path: Path
    tags_original: List[str]
    tags_current: List[str]
    is_complete: bool = False

    def is_dirty(self) -> bool:
        return self.tags_original != self.tags_current

    def added_tags(self) -> List[str]:
        return [t for t in self.tags_current if t not in self.tags_original]

    def removed_tags(self) -> List[str]:
        return [t for t in self.tags_original if t not in self.tags_current]

    def reordered(self) -> bool:
        if self.added_tags() or self.removed_tags():
            return False
        return self.tags_original != self.tags_current


@dataclass
class DatasetSummary:
    dataset_rel: str
    image_count: int
    tags: List[Dict[str, object]] = field(default_factory=list)
    images: List[Dict[str, object]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ChangeEntry:
    image_id: str
    added: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    reordered: bool = False


@dataclass
class ChangeSummary:
    dirty_images: int
    changes: List[ChangeEntry]


@dataclass
class ThumbnailCacheSettings:
    enabled: bool = False
    mode: str = "disk"
    dir_name: str = ".tag_tidy_cache"

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "ThumbnailCacheSettings":
        thumbnail_cfg = data.get("thumbnail_cache", {}) if isinstance(data, dict) else {}
        return cls(
            enabled=bool(thumbnail_cfg.get("enabled", False)),
            mode=str(thumbnail_cfg.get("mode", "disk")),
            dir_name=str(thumbnail_cfg.get("dir_name", ".tag_tidy_cache")),
        )


@dataclass
class LMStudioSettings:
    enabled: bool = False
    base_url: str = "http://localhost:1234"
    default_model: str = ""
    timeout_seconds: int = 30

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "LMStudioSettings":
        lm_cfg = data.get("lm_studio", {}) if isinstance(data, dict) else {}
        timeout_seconds = lm_cfg.get("timeout_seconds", 30)
        try:
            timeout_value = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_value = 30

        return cls(
            enabled=bool(lm_cfg.get("enabled", False)),
            base_url=str(lm_cfg.get("base_url", "http://localhost:1234")),
            default_model=str(lm_cfg.get("default_model", "")),
            timeout_seconds=timeout_value,
        )


@dataclass
class FilterCriteria:
    filename_contains: Optional[str] = None
    has_tag: Optional[str] = None
    has_undesired: Optional[bool] = None
    has_missing_required: Optional[bool] = None
    is_complete: Optional[bool] = None

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "FilterCriteria":
        if data is None:
            return cls()
        return cls(
            filename_contains=(data.get("filename_contains") or None),
            has_tag=(data.get("has_tag") or None),
            has_undesired=cls._coerce_bool(data.get("has_undesired")),
            has_missing_required=cls._coerce_bool(data.get("has_missing_required")),
            is_complete=cls._coerce_bool(data.get("is_complete")),
        )

    @staticmethod
    def _coerce_bool(value: object) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.lower()
            if lowered == "":
                return None
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off", ""}:
                return False
        return None

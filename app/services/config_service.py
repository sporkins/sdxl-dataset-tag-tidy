from __future__ import annotations

import json
from pathlib import Path
from typing import List

from app.models import ThumbnailCacheSettings


class ConfigService:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.config_path = self.base_dir / "config.json"
        self.undesired_path = self.base_dir / "undesired_tags.json"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_files()
        self.thumbnail_cache_settings = self._load_thumbnail_settings()

    def _ensure_files(self) -> None:
        if not self.undesired_path.exists():
            self.undesired_path.write_text(json.dumps({"tags": []}, indent=2), encoding="utf-8")
        if not self.config_path.exists():
            default_cfg = {
                "thumbnail_cache": {
                    "enabled": False,
                    "mode": "disk",
                    "dir_name": ".tag_tidy_cache",
                }
            }
            self.config_path.write_text(json.dumps(default_cfg, indent=2), encoding="utf-8")

    def _load_thumbnail_settings(self) -> ThumbnailCacheSettings:
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        return ThumbnailCacheSettings.from_dict(data)

    def load_undesired_tags(self) -> List[str]:
        try:
            data = json.loads(self.undesired_path.read_text(encoding="utf-8"))
            tags = data.get("tags", []) if isinstance(data, dict) else []
            if not isinstance(tags, list):
                return []
            return [self._normalize_tag(tag) for tag in tags if isinstance(tag, str) and tag.strip()]
        except Exception:
            return []

    def save_undesired_tags(self, tags: List[str]) -> None:
        normalized = [self._normalize_tag(tag) for tag in tags if tag.strip()]
        payload = {"tags": normalized}
        self.undesired_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        return tag.strip()

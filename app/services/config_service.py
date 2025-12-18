from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from app.models import ThumbnailCacheSettings


class ConfigService:
    DEFAULT_CONFIG = {
        "thumbnail_cache": {
            "enabled": False,
            "mode": "disk",
            "dir_name": ".tag_tidy_cache",
        }
    }
    DEFAULT_UNDESIRED = {"tags": []}

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.config_path = self.base_dir / "config.json"
        self.undesired_path = self.base_dir / "undesired_tags.json"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_files()
        self.thumbnail_cache_settings = self._load_thumbnail_settings()

    def _ensure_files(self) -> None:
        self._load_json_file(self.undesired_path, self.DEFAULT_UNDESIRED)
        self._load_json_file(self.config_path, self.DEFAULT_CONFIG)

    def _load_json_file(self, path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        self._write_json_file(path, default)
        return default

    def _write_json_file(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def _load_thumbnail_settings(self) -> ThumbnailCacheSettings:
        data = self._load_json_file(self.config_path, self.DEFAULT_CONFIG)
        return ThumbnailCacheSettings.from_dict(data)

    def load_undesired_tags(self) -> List[str]:
        data = self._load_json_file(self.undesired_path, self.DEFAULT_UNDESIRED)
        tags = data.get("tags", []) if isinstance(data, dict) else []
        if not isinstance(tags, list):
            self._write_json_file(self.undesired_path, self.DEFAULT_UNDESIRED)
            return []
        normalized = [self._normalize_tag(tag) for tag in tags if isinstance(tag, str) and tag.strip()]
        if normalized != tags:
            self._write_json_file(self.undesired_path, {"tags": normalized})
        return normalized

    def save_undesired_tags(self, tags: List[str]) -> None:
        normalized = [self._normalize_tag(tag) for tag in tags if isinstance(tag, str) and tag.strip()]
        payload = {"tags": normalized}
        self._write_json_file(self.undesired_path, payload)

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        return tag.strip()

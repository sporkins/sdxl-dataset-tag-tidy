from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models import LMStudioSettings, ThumbnailCacheSettings


class ConfigService:
    DEFAULT_CONFIG = {
        "dataset_root": "",
        "thumbnail_cache": {
            "enabled": False,
            "mode": "disk",
            "dir_name": ".tag_tidy_cache",
        },
        "lm_studio": {
            "enabled": False,
            "base_url": "http://localhost:1234",
            "default_model": "",
            "timeout_seconds": 30,
        },
    }
    DEFAULT_UNDESIRED = {"tags": []}

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.config_path = self.base_dir / "config.json"
        self.lm_studio_override_path = self.base_dir / "lm_studio.override.json"
        self.undesired_path = self.base_dir / "undesired_tags.json"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_files()
        self.thumbnail_cache_settings = self._load_thumbnail_settings()
        self.lm_studio_settings = self._load_lm_studio_settings()

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

    def _load_optional_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            return {}
        return {}

    def _write_json_file(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def _load_thumbnail_settings(self) -> ThumbnailCacheSettings:
        return ThumbnailCacheSettings.from_dict(self.load_config())

    def _load_lm_studio_settings(self) -> LMStudioSettings:
        return LMStudioSettings.from_dict(self.load_config())

    def load_config(self) -> Dict[str, Any]:
        config = self._load_json_file(self.config_path, self.DEFAULT_CONFIG)
        override = self._load_optional_json(self.lm_studio_override_path)
        config["lm_studio"] = self._merge_lm_studio_settings(config, override)
        return config

    def _merge_lm_studio_settings(self, config: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        default_settings = self.DEFAULT_CONFIG.get("lm_studio", {})
        config_settings = config.get("lm_studio", {}) if isinstance(config, dict) else {}
        override_settings = override.get("lm_studio", {}) if isinstance(override, dict) else {}

        safe_config_settings = config_settings if isinstance(config_settings, dict) else {}
        safe_override_settings = override_settings if isinstance(override_settings, dict) else {}
        return {**default_settings, **safe_config_settings, **safe_override_settings}

    def get_dataset_root(self) -> Optional[Path]:
        data = self.load_config()
        dataset_root = data.get("dataset_root") if isinstance(data, dict) else ""
        if not dataset_root:
            return None
        return Path(str(dataset_root)).expanduser()

    def save_dataset_root(self, path: Path) -> None:
        config = self.load_config()
        config["dataset_root"] = str(path)
        self._write_json_file(self.config_path, config)

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

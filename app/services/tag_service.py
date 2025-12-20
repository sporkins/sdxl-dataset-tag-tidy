from __future__ import annotations

from typing import Dict, List, Optional

from app.services.tagging_rules import TaggingRulesEngine, _dedupe_preserve


class TagService:
    _engine: TaggingRulesEngine | None = None

    @classmethod
    def _get_engine(cls) -> TaggingRulesEngine:
        if cls._engine is None:
            cls._engine = TaggingRulesEngine.from_default_files()
        return cls._engine

    @staticmethod
    def normalize_on_load(raw: str) -> List[str]:
        if raw is None:
            return []
        parts = [part.strip() for part in raw.split(",")]
        return [p for p in parts if p]

    @staticmethod
    def normalize_on_save(tags: List[str]) -> str:
        cleaned = [tag.strip() for tag in tags if tag.strip()]
        return ", ".join(cleaned)

    @staticmethod
    def compute_hints(tags: List[str], external_signals: Optional[Dict[str, Optional[bool]]] = None) -> Dict[str, List[str]]:
        engine = TagService._get_engine()
        hints = engine.evaluate(tags, external_signals)
        for key in ("missing_required", "possibly_missing", "not_required"):
            hints[key] = _dedupe_preserve(hints.get(key, []))
        if "info" in hints:
            hints["info"] = _dedupe_preserve(hints.get("info", []))
        return hints

    @staticmethod
    def categorize_tags(tags: List[str]) -> Dict[str, List[str]]:
        engine = TagService._get_engine()
        return engine.categorize(tags)

    @staticmethod
    def hint_options(category_id: str) -> Dict[str, object]:
        engine = TagService._get_engine()
        return engine.hint_options(category_id)

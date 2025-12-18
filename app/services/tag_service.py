from __future__ import annotations

from typing import Dict, List, Set


class TagService:
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
    def compute_hints(tags: List[str]) -> Dict[str, List[str]]:
        normalized = [t.lower() for t in tags]
        hints = {
            "missing_required": [],
            "possibly_missing": [],
            "not_required": ["background"],
        }

        has_from_behind = any("from behind" in t or "from-behind" in t for t in normalized)
        has_close_up = any(
            keyword in t
            for t in normalized
            for keyword in ["close-up", "close up", "headshot", "portrait", "bust"]
        )
        has_full_body = any("full body" in t or "full-body" in t for t in normalized)
        has_pose = any("pose" in t or t in {"standing", "sitting", "kneeling"} for t in normalized)
        has_expression = any(
            t in {"smile", "frown", "neutral expression", "open mouth", "closed mouth"} or "expression" in t
            for t in normalized
        )
        has_gaze = any("gaze" in t or "looking" in t for t in normalized)
        has_clothing = any(
            t in {"swimsuit", "dress", "coat", "shirt", "jacket", "pants", "skirt"} or "clothing" in t
            for t in normalized
        )
        has_identity = any(":" in t or t.startswith("id ") for t in normalized)
        has_framing = any(
            key in t
            for t in normalized
            for key in ["wide shot", "full body", "medium shot", "close-up", "close up", "headshot", "portrait"]
        )
        face_likely_visible = not has_from_behind

        pose_required = has_full_body or not has_close_up
        if pose_required and not has_pose:
            hints["missing_required"].append("pose")
        elif has_close_up and not has_pose:
            hints["not_required"].append("pose")

        if face_likely_visible and not has_expression:
            hints["possibly_missing"].append("expression")
        if not has_from_behind and not has_gaze:
            hints["possibly_missing"].append("gaze")
        else:
            if has_from_behind:
                hints["not_required"].extend(["expression", "gaze"])

        if not has_clothing:
            hints["missing_required"].append("clothing")
        if not has_identity:
            hints["missing_required"].append("identity token")
        if not has_framing:
            hints["missing_required"].append("framing/composition")

        # remove duplicates while preserving order
        for key in hints:
            seen: Set[str] = set()
            deduped: List[str] = []
            for item in hints[key]:
                if item not in seen:
                    seen.add(item)
                    deduped.append(item)
            hints[key] = deduped
        return hints

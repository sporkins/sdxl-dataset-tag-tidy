from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


def _canonicalize_tag(tag: str) -> str:
    cleaned = " ".join(str(tag).strip().lower().replace("-", " ").split())
    return cleaned


@dataclass
class CategoryDefinition:
    id: str
    tier: str
    cardinality_min: int
    cardinality_max: int
    applicability: str
    allowed_values: Set[str]
    preferred_values: Set[str]
    allowed_values_raw: List[str]
    preferred_values_raw: List[str]
    allows_freeform: bool

    def matches(self, tag: str) -> bool:
        canonical = _canonicalize_tag(tag)
        return canonical in self.allowed_values or canonical in self.preferred_values


class TaggingSpec:
    """
    Loads the v1 taxonomy and applicability graph.

    When adding v2, keep the loader versioned and wire the default paths in
    TagService._get_engine() so the engine can select the right spec version
    without changing call sites.
    """

    def __init__(self, taxonomy_path: Path, applicability_path: Path):
        self.taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        self.graph = json.loads(applicability_path.read_text(encoding="utf-8"))
        self.categories: Dict[str, CategoryDefinition] = {}
        self.tag_lookup: Dict[str, str] = {}
        self.singleton_categories: Set[str] = set()
        self.relaxations = []
        self.require_constraints = []
        self.forbidden_constraints = []
        self.derived_signals = {}
        self.external_signals = set()
        self.tier3_allowed: Set[str] = set()
        self._load_categories()
        self._load_constraints()

    def _load_categories(self) -> None:
        for category in self.taxonomy.get("categories", []):
            allowed_values = {_canonicalize_tag(v) for v in category.get("allowed_values", [])}
            preferred_values = {_canonicalize_tag(v) for v in category.get("preferred_values", [])}
            freeform_policy = category.get("freeform_policy") or {}
            allows_freeform = bool(freeform_policy.get("allowed", False))
            definition = CategoryDefinition(
                id=category["id"],
                tier=category["tier"],
                cardinality_min=int(category.get("cardinality", {}).get("min", 0)),
                cardinality_max=int(category.get("cardinality", {}).get("max", 1)),
                applicability=str(category.get("applicability", {}).get("when", "generally_applicable")),
                allowed_values=allowed_values,
                preferred_values=preferred_values,
                allowed_values_raw=list(category.get("allowed_values", [])),
                preferred_values_raw=list(category.get("preferred_values", [])),
                allows_freeform=allows_freeform,
            )
            self.categories[definition.id] = definition
            for value in allowed_values.union(preferred_values):
                self.tag_lookup[value] = definition.id

        tier3 = self.taxonomy.get("tier_3_allowed_tags", {})
        for info in tier3.values():
            if info.get("validation") == "exact_match_only":
                for value in info.get("allowed_values", []):
                    self.tier3_allowed.add(_canonicalize_tag(value))
            for example in info.get("examples", []):
                self.tier3_allowed.add(_canonicalize_tag(example))

        for check in self.graph.get("consistency_checks", []):
            if check.get("rule") == "no_more_than_one_value_each":
                for category in check.get("categories", []):
                    self.singleton_categories.add(category)

        for signal_id, definition in (self.graph.get("signals") or {}).items():
            if definition.get("type") == "derived":
                self.derived_signals[signal_id] = definition.get("derivation") or {}
            if definition.get("type") == "external":
                self.external_signals.add(signal_id)

    def _load_constraints(self) -> None:
        for constraint in self.graph.get("constraints", []):
            when = constraint.get("when") or {}
            require = constraint.get("require") or []
            forbid_tags = constraint.get("forbid_tags") or []
            relax = constraint.get("relax") or []
            if require:
                self.require_constraints.append((when, require))
            if forbid_tags:
                canonical_forbidden = [_canonicalize_tag(tag) for tag in forbid_tags]
                self.forbidden_constraints.append((when, canonical_forbidden))
            if relax:
                self.relaxations.append((when, relax))

    def categorize_tags(self, tags: Iterable[str]) -> Dict[str, List[str]]:
        categorized: Dict[str, List[str]] = {cid: [] for cid in self.categories}
        for tag in tags:
            canonical = _canonicalize_tag(tag)
            category_id = self.tag_lookup.get(canonical)
            if category_id:
                categorized[category_id].append(canonical)
                continue
            soft_category = self._soft_category_for_freeform(canonical)
            if soft_category:
                categorized[soft_category].append(canonical)
                continue
            if canonical in self.tier3_allowed:
                continue
        return {cid: values for cid, values in categorized.items() if values}

    def evaluate_signals(self, tags: Set[str], external_signals: Dict[str, Optional[bool]]) -> Dict[str, Optional[bool]]:
        signals: Dict[str, Optional[bool]] = {}
        for signal_id in self.external_signals:
            signals[signal_id] = external_signals.get(signal_id)
        for signal_id, derivation in self.derived_signals.items():
            signals[signal_id] = self._eval_derivation(derivation, tags)
        return signals

    def relaxed_categories(self, signals: Dict[str, Optional[bool]]) -> Set[str]:
        relaxed: Set[str] = set()
        for when, relax in self.relaxations:
            if self._condition_matches(when, signals):
                for entry in relax:
                    category = entry.get("category")
                    if category:
                        relaxed.add(category)
        return relaxed

    def _condition_matches(self, when: Dict[str, object], signals: Dict[str, Optional[bool]]) -> bool:
        signal = when.get("signal")
        expected = when.get("equals")
        if signal is None:
            return False
        value = signals.get(signal)
        if value is None:
            return False
        return value == expected

    def _eval_derivation(self, derivation: Dict[str, object], tags: Set[str]) -> Optional[bool]:
        op = derivation.get("op")
        args = derivation.get("args") or {}
        if op == "tag_present":
            tag = _canonicalize_tag(args.get("tag", ""))
            return tag in tags
        if op == "not":
            nested = self._eval_derivation(args, tags)
            return None if nested is None else not nested
        return None

    def _soft_category_for_freeform(self, canonical: str) -> Optional[str]:
        for category in self.categories.values():
            if not category.allows_freeform:
                continue
            if category.id == "arm_hand_position" and ("arm" in canonical or "hand" in canonical):
                return category.id
        return None


class TaggingRulesEngine:
    def __init__(self, spec: TaggingSpec):
        self.spec = spec

    @classmethod
    def from_default_files(cls) -> "TaggingRulesEngine":
        base = Path(__file__).resolve().parents[2]
        taxonomy_path = base / "docs" / "tagging" / "taxonomy.v1.json"
        applicability_path = base / "docs" / "tagging" / "applicability_graph.v1.json"
        spec = TaggingSpec(taxonomy_path=taxonomy_path, applicability_path=applicability_path)
        return cls(spec)

    def evaluate(self, tags: List[str], external_signals: Optional[Dict[str, Optional[bool]]] = None) -> Dict[str, List[str]]:
        normalized = [_canonicalize_tag(tag) for tag in tags if str(tag).strip()]
        tag_set = set(normalized)
        categorized = self.spec.categorize_tags(normalized)
        signals = self.spec.evaluate_signals(tag_set, external_signals or {})
        relaxed_categories = self.spec.relaxed_categories(signals)
        hints = self._build_hints(categorized, signals, relaxed_categories, tag_set)
        return hints

    def categorize(self, tags: List[str]) -> Dict[str, List[str]]:
        normalized = [_canonicalize_tag(tag) for tag in tags if str(tag).strip()]
        return self.spec.categorize_tags(normalized)

    def hint_options(self, category_id: str) -> Dict[str, object]:
        category = self.spec.categories.get(category_id)
        if not category:
            return {"category": category_id, "options": [], "allows_freeform": False}

        options: List[str] = []
        for value in category.preferred_values_raw:
            if value not in options:
                options.append(value)
        for value in category.allowed_values_raw:
            if value not in options:
                options.append(value)

        return {"category": category_id, "options": options, "allows_freeform": category.allows_freeform}

    def _build_hints(
        self,
        categorized: Dict[str, List[str]],
        signals: Dict[str, Optional[bool]],
        relaxed_categories: Set[str],
        tag_set: Set[str],
    ) -> Dict[str, List[str]]:
        missing_required: List[str] = []
        possibly_missing: List[str] = []
        not_required: List[str] = ["background"]
        forbidden: List[str] = []
        invalid: List[str] = []

        def add_if_missing(category: str, relaxed: bool = False, minimum: int = 1) -> None:
            present = len(categorized.get(category, []))
            if present < minimum:
                if relaxed:
                    not_required.append(category)
                else:
                    missing_required.append(category)

        for when, requirements in self.spec.require_constraints:
            if self.spec._condition_matches(when, signals):
                for requirement in requirements:
                    category = requirement.get("category")
                    if not category:
                        continue
                    minimum = int(requirement.get("min", 0))
                    maximum = requirement.get("max")
                    add_if_missing(category, minimum=minimum or 0)
                    if maximum is not None:
                        maximum_count = int(maximum)
                        if len(categorized.get(category, [])) > maximum_count:
                            invalid.append(category)

        face_visible = signals.get("face_visible")
        if face_visible is False:
            not_required.extend(["gaze", "expression", "mouth_state", "eyes_state"])
            for when, forbidden_tags in self.spec.forbidden_constraints:
                if self.spec._condition_matches(when, signals):
                    for tag in forbidden_tags:
                        if tag in tag_set:
                            forbidden.append(tag)

        extreme_closeup = signals.get("extreme_closeup") is True
        if "view_angle" in relaxed_categories:
            if not categorized.get("view_angle"):
                not_required.append("view_angle")
        else:
            if extreme_closeup:
                if not categorized.get("view_angle"):
                    not_required.append("view_angle")
            else:
                add_if_missing("view_angle")

        lower_body_visible = signals.get("lower_body_and_ground_contact_visible")
        pose_relaxed = "pose" in relaxed_categories or extreme_closeup
        if lower_body_visible is True:
            add_if_missing("pose", relaxed=pose_relaxed)
        elif lower_body_visible is False:
            not_required.append("pose")

        hair_visible = signals.get("hair_visible")
        if hair_visible is False:
            not_required.append("hair_style")

        for category, tags in categorized.items():
            max_count = self.spec.categories.get(category).cardinality_max
            if category in self.spec.singleton_categories or max_count == 1:
                if len(tags) > 1:
                    invalid.append(category)

        hints = {
            "missing_required": _dedupe_preserve(missing_required),
            "possibly_missing": _dedupe_preserve(possibly_missing),
            "not_required": _dedupe_preserve(not_required),
        }
        if forbidden:
            hints["forbidden"] = _dedupe_preserve(forbidden)
        if invalid:
            hints["invalid"] = _dedupe_preserve(invalid)
        return hints


def _dedupe_preserve(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    deduped: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped

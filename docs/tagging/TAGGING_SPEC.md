# SDXL Dataset Tagging Spec (v1)

This directory defines the canonical tagging taxonomy and applicability rules used to tag SDXL training datasets.

These files are intentionally tool-agnostic:
- They are not specific to a single caption model (Qwen, WD14, Florence, etc.)
- They are not specific to a particular UI or web service
- They exist so any tool can load the same source of truth and produce consistent tags and warnings

## Files

- `taxonomy.v1.json`
  - The formal taxonomy: categories, tiers, allowed values, and per-category metadata.

- `applicability_graph.v1.json`
  - A machine-readable rule graph describing derived signals (like face visibility) and how they gate requirements/forbidden tags.

- `CHANGELOG.md` (optional but recommended)
  - Track taxonomy/rule changes over time (v1 -> v2), with migration notes.

## Core definitions

### Tag
A tag is a lowercase phrase representing a single, atomic, visually observable concept.
Tags are treated as a flat set (order does not matter).

### Category
A category groups mutually exclusive tags (e.g. framing).
Most categories have a max cardinality of 1.

### Tier
Categories are assigned one of these tiers:

- Tier 1 (Hard)
  - Finite, strict allowed values
  - When applicable, must use one of the allowed values
  - No paraphrases or synonyms (consumers may normalize into canonical values)

- Tier 2 (Soft)
  - Has a preferred list, but may allow a single freeform value when none apply
  - Freeform values must still be atomic and visually obvious

- Tier 3 (Ungoverned)
  - Allowed but not validated by this taxonomy
  - Not used for completeness rules

## Applicability overview

Some categories are conditional:

- Some face-related categories are required only when the face is visible (gaze, expression).
  Mouth state is optional and should only be included when clearly discernible.
  - In v1, "from behind" implies face is not visible.
  - Future versions may add occlusion signals.

- Extreme close-ups relax composition requirements.
  - In v1, presence of the tag "close-up" implies extreme_closeup.

External signals:
- Some conditions are inherently perceptual (e.g., lower body visible, hair visible).
- The applicability graph represents those as `external` signals.
- Consumers may:
  - compute them (CV, heuristics)
  - or treat them as unknown and avoid missing-tag warnings for those gated categories

## Validation and warnings (recommended interpretation)

Consumers can use the taxonomy and graph to implement:
- Missing required categories (when applicable)
- Forbidden tag presence (based on applicability)
- Category cardinality violations (multiple values in one category)
- Optional normalization into canonical values

This spec does not mandate UI behavior. It provides the data to drive consistent behavior.

## Versioning

- Treat `taxonomy_version` and `graph_version` as immutable identifiers.
- Prefer additive evolution:
  - add new allowed values
  - add new optional categories
  - promote common freeform values into preferred/hard lists
- When breaking changes are required, bump the taxonomy version and document migration steps in CHANGELOG.

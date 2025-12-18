# API.md – SDXL LoRA Dataset Tag Tidy Web App

This document defines the HTTP contract for the v1 app described in SPEC.md.

Conventions:
- The dataset root is fixed: `C:/Zen/dev/kohya_ss/training`
- The browser never sends absolute paths.
- The browser sends `rel` paths that are always interpreted as relative to the dataset root.
- The server must normalize and validate every `rel` to prevent traversal and escaping the root.

Content types:
- HTML pages: `text/html`
- JSON APIs: `application/json`
- Images: appropriate image content type

---

## 1) HTML Pages

### GET /
Dataset Picker page
- Folder browser rooted at dataset root.
- Select a folder and load dataset.

### GET /dataset
Main Dataset View page
- Requires a dataset loaded in memory.
- If no dataset loaded, redirect to `/`.

### GET /image/{image_id}
Image Detail page

### GET /settings/undesired
Undesired tags management page

---

## 2) Folder Browser and Dataset Load APIs

### GET /api/browse?rel={rel}
List subdirectories under a relative folder path.

Query params:
- `rel` (string, optional): relative path from dataset root.
  - Missing or empty means dataset root.

Response 200 (JSON):
```json
{
  "current": { "rel": "projectA" },
  "parent": { "rel": "" },
  "dirs": [
    { "name": "sub1" },
    { "name": "sub2" }
  ],
  "summary": {
    "eligible_image_count_recursive": 42
  }
}
```

Errors:
- 400 if rel is invalid after normalization
- 404 if resolved folder does not exist
- 403 if resolved folder escapes dataset root

Notes:
- `eligible_image_count_recursive` counts images recursively under `current`.

---

### POST /api/dataset/load
Load a dataset folder into in-memory state.

Request (JSON):
```json
{
  "rel": "projectA/subset1"
}
```

Response 200 (JSON):
```json
{
  "dataset_rel": "projectA/subset1",
  "image_count": 120,
  "tag_total_unique": 843,
  "warnings": []
}
```

Errors:
- 400 invalid rel
- 404 folder not found
- 422 if:
  - no images found
  - image_count > 200

---

## 3) Dataset Data APIs

### GET /api/dataset/summary
Returns the in-memory dataset summary.

Response 200 (JSON):
```json
{
  "dataset_rel": "projectA/subset1",
  "image_count": 120,
  "tags": [
    { "tag": "swimsuit", "count": 55, "is_undesired": false },
    { "tag": "1girl", "count": 120, "is_undesired": true }
  ],
  "images": [
    {
      "image_id": "abc123",
      "filename": "1172_Back.jpg",
      "rel_path": "sub/1172_Back.jpg",
      "tag_count": 18,
      "has_undesired": true,
      "hints": {
        "missing_required": ["pose"],
        "possibly_missing": ["expression"],
        "not_required": ["expression"]
      }
    }
  ]
}
```

Notes:
- `image_id` is an opaque stable ID for the current in-memory dataset load.
- `rel_path` is for informational display only; use `image_id` for image serving APIs.

---

### GET /api/image/{image_id}/tags
Get the staged (current) tag list for one image.

Response 200:
```json
{
  "image_id": "abc123",
  "tags": ["tag1", "tag2", "tag3"],
  "is_dirty": true
}
```

Errors:
- 404 if image_id unknown

---

## 4) Staging APIs (No disk writes until apply)

### POST /api/ops/bulk
Stage a bulk tag edit.

Request (JSON):
```json
{
  "scope": {
    "mode": "all|filtered|selected",
    "filter": {
      "filename_contains": "string|null",
      "has_tag": "string|null",
      "has_undesired": true|false|null,
      "has_missing_required": true|false|null
    },
    "selected_image_ids": ["abc", "def"]
  },
  "op": {
    "type": "add|delete|replace",
    "tag": "tag_to_add_or_delete",
    "old_tag": "old_tag_if_replace",
    "new_tag": "new_tag_if_replace"
  }
}
```

Response 200:
```json
{
  "affected_images": 42,
  "summary": { "added": 42, "removed": 0, "replaced": 0 }
}
```

Notes:
- Exact string match only.
- No implicit case folding.
- Adds are idempotent (no duplicates).

---

### POST /api/image/{image_id}/ops
Stage a per-image edit.

Request examples:
- Add:
```json
{ "type": "add", "tag": "newtag" }
```

- Delete:
```json
{ "type": "delete", "tag": "oldtag" }
```

- Reorder:
```json
{ "type": "reorder", "tags": ["t1", "t2", "t3"] }
```

Response 200:
```json
{ "image_id": "abc123", "is_dirty": true }
```

Errors:
- 404 if image_id unknown
- 422 if reorder tags set does not match current set (must be same elements, different order)

---

### GET /api/changes
Get staged change summary.

Response 200:
```json
{
  "dirty_images": 12,
  "changes": [
    {
      "image_id": "abc123",
      "added": ["x"],
      "removed": ["y"],
      "reordered": true
    }
  ]
}
```

---

### POST /api/changes/apply
Write all staged changes to disk by updating sidecar `.txt` files.

Response 200:
```json
{ "applied": true, "written_files": 12 }
```

Rules:
- Normalize formatting on save (see SPEC.md)
- If an image has no sidecar file, create it.

---

### POST /api/changes/discard
Discard all staged changes and revert to original loaded state.

Response 200:
```json
{ "discarded": true }
```

---

## 5) Undesired Tags APIs

### GET /api/undesired
Response 200:
```json
{ "tags": ["tag1", "tag2"] }
```

### POST /api/undesired/add
Request:
```json
{ "tag": "some_tag" }
```
Response:
```json
{ "ok": true }
```

### POST /api/undesired/remove
Request:
```json
{ "tag": "some_tag" }
```
Response:
```json
{ "ok": true }
```

Rules:
- Persist to `config/undesired_tags.json`
- No replace endpoint

---

## 6) Image Bytes Endpoints

### GET /img/thumb/{image_id}?w=256
- Returns a thumbnail (generated and optionally cached)
- `w` is optional; default 256
- Maintain aspect ratio

### GET /img/full/{image_id}
- Returns original image bytes

Rules:
- Validate image_id maps to a file under the loaded dataset directory.
- Never read files outside the loaded dataset directory.

---

## 7) Error Format (JSON APIs)
For JSON endpoints, return errors as:

```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human friendly message"
  }
}
```

Use appropriate HTTP status codes (400/403/404/422/500).

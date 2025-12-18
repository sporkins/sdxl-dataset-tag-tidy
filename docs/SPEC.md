# SDXL LoRA Dataset Tag Tidy Web App – SPEC

## 0. Goal
Build a Python-based web app that runs locally on a Windows PC and is accessible over the local LAN from a mobile browser. The app is used to review, clean, and edit existing SDXL LoRA dataset tags stored as sidecar `.txt` files next to images.

This app is a manual dataset hygiene tool, not an AI tagging system.

---

## 1. Hard Constraints
- Python backend
- No database
- No authentication
- No cloud dependencies
- No AI inference
- No GPU usage
- No persistent session state about loaded datasets
- Mobile-first UI (touch-only; no mouse assumptions)
- All tag changes must be staged until explicitly saved
- Max dataset size: 200 images

---

## 2. Filesystem Assumptions (Fixed)
- The web app lives under:
  - `C:/Zen/dev`
- All datasets live under:
  - Configured via `config/config.json` (git-ignored). Recommended value: `C:/Zen/dev/kohya_ss/training`.
- All filesystem access must be constrained to that dataset root.

---

## 3. Dataset Format
- Images may be in nested subfolders.
- Supported image extensions:
  - `.png`, `.jpg`, `.jpeg`, `.webp`
- Each image has a sidecar tag file:
  - Same basename, `.txt` extension
  - Example: `image.png` → `image.txt`
- Tag file format:
  - Single line
  - Comma-separated tags

### Tag normalization rules
On load:
- Split by comma
- Trim whitespace
- Drop empty tags
- Preserve original order

On save:
- Trim whitespace
- Drop empty tags
- Join with `", "` (comma + single space)
- Preserve user-defined order

---

## 4. Directory Selection (No Pasted Paths)
- The user selects a dataset directory using a server-side folder browser UI.
- The UI starts at the configured dataset root.
- The user taps through folders to select a dataset.
- Free-form path input and pasted paths are forbidden.

### Validation
- Selected path must:
  - Exist
  - Be a directory
  - Be under the dataset root
- Dataset is rejected if:
  - No images found
  - More than 200 images found

---

## 5. Core UI Pages

### 5.1 Dataset Picker Page
- Folder tree browser starting at dataset root
- Breadcrumb navigation
- “Select this folder” button
- “Load dataset” button
- Clear error messages for invalid selections

---

### 5.2 Main Dataset View
Mobile-first layout.

Displays:
- Scrollable grid/list of image thumbnails
- Filename
- Tag count
- Indicators:
  - Contains undesired tags (red)
  - Missing required categories (yellow)
  - Possibly missing categories (yellow outline)

Global tag panel:
- All tags with counts
- Searchable
- Sortable
- Undesired tags highlighted red
- Tap a tag to filter images

Filters:
- By filename substring
- By tag present
- By “has undesired tags”
- By “missing required categories”

---

### 5.3 Image Detail Page
- Large image preview
- Editable tag list:
  - Add tag
  - Delete tag
  - Reorder tags via touch drag
- Category hints displayed
- Undesired tags highlighted

---

## 6. Bulk Operations (Staged)
Bulk operations apply to:
- All images
- Filtered images
- Manually selected images

Supported operations:
- Bulk add tag
- Bulk delete tag
- Bulk replace tag (exact match)

Rules:
- No disk writes on operation
- Changes are staged in memory
- User can review changes
- User must explicitly apply or discard changes

---

## 7. Staging & Change Review
- All changes are staged until saved
- A global “Pending Changes” panel shows:
  - Number of dirty images
  - Tags added / removed / replaced
- Buttons:
  - Apply changes (writes `.txt` files)
  - Discard changes (revert in memory)

---

## 8. Global Undesired Tag List (Persistent)
- Persistent list stored in JSON
- Tags in this list:
  - Highlighted red everywhere
  - Trigger image-level warnings
- User can:
  - Add undesired tags
  - Remove undesired tags
- Replace is NOT supported

---

## 9. Tag Categories & Hint Rules

### Removed Categories (do not implement)
- Subject type (1girl, 1boy, male, female, etc)
- Eye color
- Hair color
- Style / quality

### Active Categories
- Identity token(s) (configurable)
- Framing / composition
- Face visibility
- Eyes / gaze / eye state (NOT color)
- Expression
- Pose
- Clothing
- Background (optional; never required)

### Hint heuristics
- From-behind → expression and gaze not required
- Close-up / headshot → pose not required
- Full body → pose required
- Face likely visible and no expression → possibly missing expression
- No gaze tags and not from-behind → possibly missing gaze
- Background is never required

Hints are advisory only.

---

## 10. Image Serving & Security
- Images may be outside the app code directory
- Image serving endpoints must:
  - Validate resolved path
  - Ensure it is under selected dataset root
- Prevent path traversal and symlink escapes

---

## 11. Performance
- Max 200 images
- Use thumbnails in main view
- Full image only on detail view
- Thumbnail caching allowed (disk or memory)

---

## 12. Technology Guidance
- Backend: FastAPI
- Templates: Jinja2
- Interactivity: HTMX
- Touch drag reorder: SortableJS

---

## 13. Configuration Files

### `config/undesired_tags.json`
```json
{
  "tags": []
}
```

### Optional thumbnail cache config
```json
{
  "thumbnail_cache": {
    "enabled": true,
    "mode": "disk",
    "dir_name": ".tag_tidy_cache"
  }
}
```

---

## 14. Deliverables
- Fully working LAN-accessible web app
- Mobile-first UI
- Safe filesystem handling
- README with run instructions

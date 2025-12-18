# SDXL Dataset Tag Tidy

A mobile-first FastAPI utility for browsing SDXL LoRA datasets, reviewing tags, and staging edits before writing updated sidecar files.

## Requirements
- Python 3.11+
- pip

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the app

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` on your LAN device. The UI is touch-friendly and uses HTMX and SortableJS for interactions.

## Filesystem expectations
- Dataset root is fixed to `C:/Zen/dev/kohya_ss/training`.
- Folder selection is done via the built-in browser; free-form path entry is disabled.
- Datasets over 200 images are rejected.
- Tag files are `.txt` sidecars using comma-separated values.

## Staging and persistence
- Tag edits (bulk or per-image) are staged in memory only.
- Use **Apply** to write normalized tags back to sidecar files (`, ` separator).
- Use **Discard** to revert to the originally loaded tags.
- Undesired tags are persisted to `config/undesired_tags.json`.

## Configuration
- `config/config.json` toggles optional thumbnail caching (disk mode, disabled by default).
- `config/undesired_tags.json` stores the global undesired tag list in the format `{ "tags": [] }`.

## Project layout
- `app/main.py` – FastAPI app wiring and middleware
- `app/deps.py` – shared dependencies and dataset root definition
- `app/models.py` – shared dataclasses and constants
- `app/services/` – config loader, dataset manager, tag normalization and hints
- `app/routes/` – HTML, API, and image-serving routes
- `app/templates/` – Jinja2 templates (HTMX-driven, mobile-first)
- `app/static/` – CSS and JS assets

## Notes
- Thumbnail endpoints validate paths against the loaded dataset and respect optional cache settings.
- Tag hint heuristics follow the rules in `docs/SPEC.md` and highlight missing or optional categories.

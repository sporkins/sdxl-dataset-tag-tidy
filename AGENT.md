# AGENT.md

You are building a Python web app defined by SPEC.md.

## Obey these rules strictly

- Python backend only
- Use FastAPI
- No database
- No authentication
- No cloud services
- No AI inference
- Mobile-first UI
- Touch-only interactions (no mouse assumptions)
- Max dataset size: 200 images
- Analyze is optional, uses only a local LM Studio backend, never writes or stages automatically, and requires explicit user approval before staging suggested changes
- All datasets are under:
  C:/Zen/dev/kohya_ss/training

## Directory selection
- Do NOT accept pasted paths or free-form input
- Implement a server-side folder browser starting at the dataset root
- Validate all paths are under the dataset root

## Tag handling
- Tags live in sidecar .txt files
- Comma-separated
- Preserve order
- Normalize on save with ", " separator

## Staging
- Never write tag files immediately
- All changes must be staged in memory
- User must explicitly Apply or Discard changes

## Undesired tags
- Persisted in JSON
- Highlight red everywhere
- Allow add/remove only

## Categories
- Implement ONLY categories listed in SPEC.md
- Do NOT add subject type, eye color, hair color, or style categories
- Background is optional and never required

## UX
- Mobile-first layouts
- Use HTMX for interactions
- Use SortableJS for touch drag reorder

## Do not
- Invent new features
- Ask clarifying questions
- Change filesystem assumptions
- Add AI-based tagging
- Introduce databases or user accounts

## Deliverables
- Working FastAPI app
- Templates and static assets
- Safe image serving
- README with run instructions

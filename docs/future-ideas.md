# Future Ideas — The War Table

Ideas that are intentionally deferred. Not forgotten — just waiting for the right phase.

---

## Configurable AI Token Limits (Settings Page) — PLANNED

Full implementation plan saved to `docs/ai-token-limits-plan.md`. Three grouped settings (standard, generate, assistant) with multipliers for large entity types. Helper function `_get_max_tokens()` in ai.py. No migration needed — uses AppSetting.

---

## Theme Engine — PLANNED

Full implementation plan saved to `docs/theme-engine-plan.md`. Dark (current), Light, High Contrast, and Parchment (stretch). Uses dual-attribute approach (`data-bs-theme` + `data-wt-theme`), CSS custom properties, localStorage per-browser, no migration needed. ~11 files, ~3 new files.

---

## Session Mode Dashboard — Phase 15b (Advanced Layout)

**Why deferred:** Core dashboard (Phase 12) and site content panel (Phase 15a) are done. These enhancements add significant complexity and are "nice to have" rather than essential.

**Features:**

### Drag-to-Rearrange Panels
- Dashboard panels (Notes, NPCs, Encounters, Site Content, etc.) can be dragged into a custom order
- Layout saved to `localStorage` per user, keyed to campaign ID
- Library: HTML5 drag-and-drop or a lightweight library like SortableJS

### Dashboard Presets ("Combat Mode")
- Named layout presets that show/hide and reorder panels in one click
- Example presets: "Exploration" (Site Content prominent), "Combat" (Encounters + NPCs front), "Roleplay" (Notes + NPC chat full width)
- Presets stored in `AppSetting` as JSON; user can create and save their own

### Map Overlay Viewer
- Floating, resizable image overlay for a location/site map during play
- GM can open a map without leaving the dashboard
- Image sourced from the linked Adventure Site or Location's `map_filename`
- Implemented as a draggable Bootstrap modal or a custom overlay `<div>`

**Notes:**
- SortableJS is a small, no-dependency library that integrates well with Bootstrap grid layouts
- Presets could reuse the `AppSetting` key/value model already in place
- Map overlay needs no new model — just a JS panel that loads an existing image URL

---

## ~~Activity Log / Event Viewer~~ — DONE (PR #37)

Implemented in `feature/activity-log`. See `docs/activity-log-plan.md` for full details.

---

## Campaign Assistant → "Link to Story Arc" Quick-Action — PLANNED

Full implementation plan saved to `docs/assistant-arc-link-plan.md`. Persistent Story Arc dropdown at top of chat page; `story_arc_id` set on save. Optional arc context injection into AI prompt. No migration needed — FK already exists.

---

## Pinned Entities with Inline Edit (Session Mode) — PLANNED

Full implementation plan saved to `docs/pinned-entities-plan.md`. Pin/unpin API on Session model. 3 new JSON columns (location, quest, item) plus wiring up existing unused `pinned_npc_ids`. Dashboard panel with condensed cards. Migration required.

---

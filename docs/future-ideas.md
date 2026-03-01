# Future Ideas — The War Table

Ideas that are intentionally deferred. Not forgotten — just waiting for the right phase.

---

## Configurable AI Token Limits (Settings Page)

**Why deferred:** Token limits are currently hardcoded in `app/routes/ai.py`. They've been tuned per entity type (e.g. 4096 for adventure sites, 2048 for NPCs), but a power user with a fast/expensive model may want to push limits higher, and a user on a budget may want to cap them lower.

**The right approach:**
- Add per-feature token limit fields to the Settings page under the AI section
- Store them in `AppSetting`: `ai_max_tokens_generate`, `ai_max_tokens_smart_fill`, `ai_max_tokens_assistant`
- `ai_chat()` (or the individual routes) reads the setting and falls back to the hardcoded default if not set
- Input type `number`, min 256, max 8192, step 256 — with a note on what each feature uses them for

**Nice to have:** A "large entity types" override — a separate token cap specifically for `adventure_site` and `bestiary` Generate Entry calls, since those produce much more content than NPC/location/quest entries.

**Notes:**
- No migration needed if `AppSetting` model already supports arbitrary key/value pairs (it does)
- Anthropic Claude Haiku supports up to 8192 output tokens; Ollama depends on the loaded model's context window
- Current hardcoded values: Smart Fill = 1024, Generate Entry = 2048 (8000 for adventure_site, 4096 for bestiary)

---

## Theme Engine

**Why deferred:** A single high-contrast CSS toggle is not the right approach. Adding one-off overrides creates maintenance debt and doesn't scale.

**The right approach:** A proper theme engine where:
- Each theme is a named CSS variable set (or a separate CSS file)
- Themes are stored in `AppSetting` as `ui_theme = 'dark' | 'high_contrast' | 'light' | ...`
- The active theme is applied via a `data-theme` attribute on `<html>` (or a CSS class)
- `base.html` reads the theme from a context processor injected in `app/__init__.py`
- Settings page lets the user pick a theme from a dropdown or visual swatch
- New themes can be added by dropping a new CSS file into `app/static/css/themes/`

**Supported themes to build toward:**
- `dark` — current default
- `high_contrast` — brighter text, sharper borders, for use at dim game tables
- `light` — for daytime use or accessibility preference
- `parchment` — sepia/fantasy aesthetic (stretch goal)

**Notes:**
- Bootstrap 5.3 `data-bs-theme` only supports `light` and `dark` natively; custom themes need CSS custom property overrides
- Consider using CSS `@layer` to keep theme overrides isolated from component styles
- No migrations needed — `AppSetting` model already exists

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

## Activity Log / Event Viewer

**Why deferred:** Useful for debugging and for GMs who want to review what changed and when. Not essential for core gameplay.

**The right approach:**
- A lightweight `ActivityLog` model: `id`, `user_id`, `campaign_id`, `action` (string), `entity_type`, `entity_id`, `entity_name`, `timestamp`
- Log writes on key events: entity created, entity edited, entity deleted, session started/ended, status changed (NPC died, quest completed), AI generation triggered
- Log writes happen in route handlers — a small `log_event(action, entity_type, entity_id, entity_name)` helper keeps it DRY
- Admin-only viewer page at `/admin/activity-log` — filterable by campaign, entity type, date range, and user
- Optional: per-campaign GM log at `/campaigns/<id>/activity` showing recent changes to that campaign's entities
- Entries auto-purge after a configurable number of days (stored in `AppSetting`)

**What it helps with:**
- "Who changed this NPC's status and when?"
- "What entities were touched in the last session?"
- "Did the AI generation run successfully?"
- Debugging unexpected data changes on the Unraid server

**Notes:**
- Write operations should be fire-and-forget (catch exceptions silently so a log failure never breaks a save)
- Keep log entries lightweight — no storing full diffs, just the action and entity reference
- Migration needed: new `activity_log` table
- Consider a max-rows limit per campaign to prevent unbounded growth on SQLite

---

## Pinned Entities with Inline Edit (Session Mode)

**Why deferred:** The dashboard already shows NPCs and the active site. Pinning adds flexibility but also UI complexity.

**The idea:**
- GM can "pin" any entity (NPC, location, item, quest) to the dashboard sidebar for quick reference during a session
- Pinned entities show a condensed card: name, status, one-line description
- Optional inline edit of status field directly from the pin card (no navigation away)
- Pins stored in `localStorage` or as a JSON field on the `Session` model

---

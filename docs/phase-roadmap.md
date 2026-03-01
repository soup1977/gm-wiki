# The War Table — Phase Roadmap (13–16)

Phases 1–8 complete. Phases 9–12 complete.

---

## Phase 13: UX Polish & Visual Indicators

**Goal:** Consistent status colors, progress bars, campaign roll-ups, search improvements.

| Feature | Effort | Notes |
|---------|--------|-------|
| Standardized status color scheme | Small | CSS custom properties for consistent Green/Yellow/Red across all entity lists and details |
| Progress bars on Adventure Sites | Small | Bootstrap 5 `<div class="progress">` on list and detail views from `progress_pct` |
| Campaign-level progress roll-up | Small | Aggregate stats on Campaign detail: "X/Y Sites done", active quest count, overall progress |
| Search results grouped by entity type | Medium | Group global search results by entity type with count badges and collapsible sections |
| Wiki visibility quick-toggle | Small | Toggle button on Session Mode dashboard for active session entities |

**Key files:** `app/static/css/custom.css`, Site/Campaign templates, `app/routes/global_search.py`
**Dependencies:** Phase 9 (progress data), Phase 10 (hierarchy display)

---

## Phase 14: AI Runtime Features (At the Table)

**Goal:** AI features for live play — expanded NPC chat, improv encounters, hazard flavor, consequence suggestions.

| Feature | Effort | Notes |
|---------|--------|-------|
| Multi-turn NPC Chat | Medium | Store conversation history in Flask session by NPC ID (follow Campaign Assistant pattern). Chat-like UI with message history |
| On-the-fly encounter generation | Medium | "Improv Encounter" button → location + context → quick combat encounter card |
| Dynamic hazard flavor text | Small | On timer/counter event → short sensory description (256 max tokens, one-shot) |
| AI consequence suggestions | Small | Post-wrap-up → "Suggest Consequences" → 2-3 narrative ripple effects |
| AI milestone suggestions | Small | Site detail → "Suggest Milestones" → breakpoints from content headings |

**Key files:** `app/routes/session_mode.py`, `app/routes/ai.py`, dashboard template, new JS for chat UI
**Dependencies:** Phase 9, Phase 11, Phase 12

---

## Phase 15: Dashboard Overhaul (Digital GM Screen)

**Goal:** Transform Session Mode into a modular, panel-based dashboard optimized for tablet play.

| Feature | Effort | Notes |
|---------|--------|-------|
| Panel-based layout (Main/Toolkit/Controls) | Large | 50/30/20 split. Responsive: stack vertically on portrait tablets |
| Adventure Site content in main panel | Medium | Render linked Site Markdown with sticky ToC in the main panel |
| Shortcode popup previews | Medium | Hover/click entity links → popup card with key fields. New `GET /api/entity-preview/<type>/<id>` endpoint |
| Pinned entities panel with inline edit | Medium | Toolkit section showing session-pinned entities with AJAX-saveable fields |
| Map overlay viewer | Small | Zoomable fullscreen modal for location maps. `CSS transform: scale()` |
| Dashboard presets ("Combat Mode") | Medium | Toggle buttons that resize panels. Preference stored in localStorage |
| Drag-to-rearrange panels | Medium | SortableJS or native HTML5 drag-and-drop for panel reordering |

**Key files:** `app/templates/session_mode/dashboard.html` (major restructure), `app/routes/session_mode.py`, new JS files, `app/static/css/custom.css`
**Dependencies:** Phase 9, 12, 14 — this is the capstone phase

Build incrementally: (1) Site content in dashboard → (2) panel layout → (3) popup previews → (4) presets/drag → separate PRs each

---

## Phase 16: Workflow Guidance & Campaign Tools

**Goal:** Onboarding wizards, planning checklists, entity grouping views, accessibility themes.

| Feature | Effort | Notes |
|---------|--------|-------|
| Campaign setup wizard | Medium | Multi-step modal on campaign creation: theme, world context, first faction/location/site |
| Adventure planning sidebar checklist | Small | Checklist in Site editor: "Add Sections", "Link Entities", etc. (localStorage) |
| Campaign entity grouping view | Medium | Tag-based and status-based grouping view for campaign entities (Quests by status, NPCs by faction, Sites by status). Filterable, collapsible groups — similar to Location's grouped list but across entity types on the Campaign detail page |
| "Next Step" transition buttons | Small | Contextual buttons: "Start New Site", "Plan Session", "Enter Run Mode", "Wrap Up" |
| High-contrast theme option | Small | CSS custom properties toggle via Settings. `[data-theme="high-contrast"]` on `<html>` |

**Key files:** Campaign/Site form templates, `app/templates/campaigns/detail.html`, `app/static/css/custom.css`
**Dependencies:** Phase 9, 10

---

## Dependency Graph & Recommended Order

```
Phase 9 (Data Foundations)  ←  COMPLETE
  ├──→ Phase 10 (Navigation Improvements)  ←  COMPLETE
  │     ├──→ Phase 13 (UX Polish)
  │     └──→ Phase 16 (Workflow Guidance)
  │
  ├──→ Phase 11 (AI Content Gen)  ←  COMPLETE
  │     └──→ Phase 12 (Session Workflow)  ←  COMPLETE
  │           └──→ Phase 14 (AI Runtime)
  │
  └──→ Phase 15 (Dashboard Overhaul) ← after Phases 12 + 14
```

Parallel tracks possible:
- Phases 13 + 14 can run simultaneously (different file sets)
- Phase 16 can start anytime after Phase 10

## Effort Summary

| Phase | Sessions (est.) | Description |
|-------|----------------|-------------|
| 9 | 3-5 | Data foundations |
| 10 | 3-5 | Navigation & breadcrumbs |
| 11 | 12-15 | AI content generation |
| 12 | 10-14 | Session workflow |
| 13 | 7-10 | UX polish |
| 14 | 10-14 | AI runtime features |
| 15 | 20-28 | Dashboard overhaul |
| 16 | 8-12 | Workflow guidance |
| **Total** | **~69-99** | |

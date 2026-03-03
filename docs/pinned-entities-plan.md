# Pinned Entities — Session Mode Dashboard

## Context

The Session Mode dashboard shows NPCs and the active adventure site, but the GM can't pin arbitrary entities for quick reference. Pinning lets the GM keep a handful of locations, quests, or items visible during play without navigating away from the dashboard.

**Branch:** `feature/pinned-entities`

---

## Current State

- `Session.pinned_npc_ids` — JSON column already exists in the model (`models.py:419`) but is **unused** in any route or template
- Session Mode dashboard: `app/routes/session_mode.py` + `app/templates/session_mode/dashboard.html`
- No pinned columns exist for locations, quests, or items

---

## Design

### New JSON Columns on Session Model

Add 3 new JSON columns (matching the existing `pinned_npc_ids` pattern):
- `pinned_location_ids` — JSON array of Location IDs
- `pinned_quest_ids` — JSON array of Quest IDs
- `pinned_item_ids` — JSON array of Item IDs

**Migration required** — 3 new nullable JSON columns on the `sessions` table.

### Dashboard Panel

Add a "Pinned Entities" panel between the Quick Launch section and Encounters on the Session Mode dashboard. Layout:

```
┌─ Pinned Entities ────────────────────────────┐
│ [NPC icon] Grukk the Merchant    [unpin ×]   │
│ [Location icon] The Rusty Anvil  [unpin ×]   │
│ [Quest icon] Find the Lost Gem   [unpin ×]   │
│ [Item icon] Sword of Dawn        [unpin ×]   │
│                                              │
│ [+ Pin Entity] (dropdown: NPC/Location/...)  │
└──────────────────────────────────────────────┘
```

Each pinned card shows:
- Entity icon + name (clickable link to detail page)
- One-line description or status
- Unpin button (×)

### Pin/Unpin API

New route in `session_mode.py`:

```
POST /session-mode/pin
Body: { "entity_type": "npc", "entity_id": 42 }
Response: { "ok": true }

POST /session-mode/unpin
Body: { "entity_type": "npc", "entity_id": 42 }
Response: { "ok": true }
```

These read the current session's `pinned_*_ids` JSON array, add/remove the ID, and save.

### Pin Buttons on Entity Cards

Add a small pin icon button on entity detail pages and list pages. When clicked, AJAX call to the pin endpoint. Visual feedback: icon toggles between outline (unpinned) and filled (pinned).

---

## Files to Create/Modify

| File | Action | Change |
|------|--------|--------|
| `app/models.py` | Modify | Add 3 JSON columns to Session |
| `migrations/versions/xxxx_add_pinned_entity_columns.py` | **Create** | Migration for 3 new columns |
| `app/routes/session_mode.py` | Modify | Add pin/unpin endpoints; pass pinned entities to dashboard template |
| `app/templates/session_mode/dashboard.html` | Modify | Add Pinned Entities panel |
| `app/templates/npcs/detail.html` | Modify | Add pin button |
| `app/templates/locations/detail.html` | Modify | Add pin button |
| `app/templates/quests/detail.html` | Modify | Add pin button |
| `app/templates/items/detail.html` | Modify | Add pin button |

---

## Implementation Steps

1. Add 3 JSON columns to Session model
2. Write and run migration
3. Add pin/unpin API endpoints in `session_mode.py`
4. Add Pinned Entities panel to dashboard template
5. Add pin toggle buttons to entity detail templates
6. Add JS for pin/unpin AJAX calls and visual feedback
7. Wire up the existing `pinned_npc_ids` column (currently unused)

---

## Verification

1. Start a session → pin an NPC → dashboard shows the NPC in Pinned panel
2. Pin a location, quest, and item → all 4 types appear
3. Unpin an entity → it disappears from the panel
4. Refresh the page → pins persist (stored in DB on Session)
5. End session and start a new one → new session has empty pins
6. Pin button on detail page toggles correctly (filled = pinned, outline = not)
7. Pinned entity names link to the correct detail pages

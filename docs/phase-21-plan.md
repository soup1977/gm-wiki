# Phase 21— Campaign/Adventure Hierarchy: Documentation & Alignment

## Context

The GM has articulated the intended mental model clearly:

> Campaigns contain everything. Adventures scope down from campaigns — there can be 1 to 100+ per campaign. Quests range from campaign-spanning story arcs to room-level objectives. "Rooms" are really any focused location within the world for this adventure and act — a bar, a dungeon, an overland hex. Adventures have a beginning, middle, and end (the Acts). NPCs and Items follow the same campaign → adventure scope chain.

This phase locks in that model as a written specification, verifies the app matches it, and fixes any terminology or relationship gaps.

---

## The Canonical Hierarchy

```
Campaign
├── Adventures (many per campaign)
│   ├── Act 1: Beginning
│   │   ├── Scene (a physical area: dungeon, town, forest...)
│   │   │   ├── Area  ← renamed from "Room" in UI
│   │   │   └── Area
│   │   └── Scene
│   ├── Act 2: Middle
│   └── Act 3: End (or however many acts the story needs)
│
├── NPCs (campaign-wide; optionally scoped to an adventure)
├── Locations (campaign-wide; scenes can reference them)
├── Quests
│   ├── Campaign quests (span multiple adventures: main arc, backstory, etc.)
│   └── Adventure quests (scoped to one adventure; linked via adventure_id)
├── Items (campaign-wide; optionally scoped to an adventure)
├── Factions (campaign-wide)
└── Sessions (link to an adventure when running one)
```

### Scope rules
| Entity | Campaign-scoped | Adventure-scoped | How linked |
|---|---|---|---|
| NPC | `adventure_id = null` | `adventure_id = X` OR via `adventure_npc_link` | Direct FK or M-to-M |
| Location | `adventure_id = null` | `adventure_id = X` | Direct FK |
| Quest | `adventure_id = null` | `adventure_id = X` OR via `adventure_quest_link` | Direct FK or M-to-M (Phase 20f) |
| Item | `adventure_id = null` | `adventure_id = X` | Direct FK |
| Faction | campaign-only | linked via `adventure_faction_link` | M-to-M |
| Session | campaign-scoped | `adventure_id = X` | Direct FK |

---

## Unified "Location" Concept

**The core insight:** A campaign Location, an adventure Scene, and an adventure Room are all the same thing — a *place* in the world, just at different zoom levels and different levels of adventure detail.

- **Campaign Location** = the canonical place record ("The Crimson Throne Inn", "The Vault of Shadows"). Lives in the world forever.
- **Adventure Room** = the GM-runnable view of a place during this adventure — read-aloud text, GM notes, creatures, loot. It IS that Location, focused for play.

**Rename in UI:** Change all "Room" labels to **"Location"** throughout adventure templates.
- DB table stays `adventure_room` (no migration risk)
- Python variable names (`room`, `rooms`) stay as-is internally
- Jinja labels: `Room` / `Rooms` → `Location` / `Locations` everywhere in adventure templates
- The key field ("A1", "B3") stays — still useful as a shorthand reference

**Link adventure Locations to campaign Locations (Gap 1 = YES):**
Add `location_id` (optional FK to `locations.id`) on `AdventureRoom`. When a GM creates or edits an adventure location, they can:
1. Link it to an existing campaign Location (e.g. "This is The Crimson Throne Inn")
2. Or leave it standalone (new unnamed place that may or may not get promoted)

The location card in the runner shows the campaign Location name as a link when linked.

**Files affected:** `runner.html`, `detail.html`, `_room_card.html`, `edit_room.html`, `list.html`, `draft_review.html`, `create.html` (labels only); `models.py` + migration (location_id FK)

---

## Deliverable 1: Data Model Document

Write `docs/data-model.md` — the canonical reference for the hierarchy. Includes:
- Entity definitions and purpose
- Relationship diagram (ASCII)
- Scope rules table (above)
- Naming conventions (Area vs Room, Session vs GameSession in code, etc.)
- Quest scope explanation
- NPC dual-link explanation (adventure_id vs adventure_npc_link)

---

## Deliverable 2: CLAUDE.md Update

Update the "Entity Types" section to reflect:
- Accurate entity descriptions matching the hierarchy
- Note that "Room" in code/DB = "Area" in UI
- Quest scope description (campaign vs adventure)
- Adventure structure (Acts → Scenes → Areas)

---

## Deliverable 3: App Alignment Checks

Walk through each entity and verify the app matches the model. Known gaps to fix:

### Gap 1: Adventure Location ↔ Campaign Location link
**Resolved above** — add optional `location_id` FK to `AdventureRoom` so each adventure location can be tied to its campaign Location counterpart. Scenes already have `location_id`; now rooms/locations get it too.

### Gap 2: NPC dual-link clarification
Two ways an NPC can be associated with an adventure:
- `npc.adventure_id = X` — NPC was *created for* this adventure (adventure-specific)
- `adventure_npc_link` — existing campaign NPC is *featured in* this adventure (key NPC)
The Entities tab on the adventure detail page should clearly show both groups with labels ("Created for this adventure" vs "Featured NPCs from campaign").

### Gap 3: Session → Adventure link surfacing
Sessions have `adventure_id`. The Session detail page should prominently show which adventure it belongs to, and the adventure detail page should list sessions run for it. Currently this link exists in DB but may not be surfaced in UI.

---

## Files to Create/Modify

| File | Change |
|---|---|
| `docs/data-model.md` | **Create** — canonical hierarchy reference |
| `CLAUDE.md` | Update Entity Types section |
| `app/templates/adventures/*.html` | Rename "Room" → "Location" in all display labels |
| `app/models.py` | Add optional `location_id` FK to `AdventureRoom` (campaign Location link) |
| `migrations/versions/` | Migration for AdventureRoom.location_id |
| `app/templates/adventures/detail.html` | Clarify NPC dual-link groups (Gap 2); surface session list (Gap 3) |
| `app/templates/sessions/detail.html` | Show linked adventure name/link (Gap 3) |

---

## Verification

1. `docs/data-model.md` exists and matches the hierarchy described above
2. All "Room" labels in the runner, detail, and edit pages now read "Location"
3. An adventure Location can be optionally linked to a campaign Location — shows the name as a link in the location card
4. Adventure detail Entities tab groups NPCs as "Adventure-Specific" vs "Featured from Campaign"
5. Session detail page shows "Part of Adventure: [Name]" when adventure_id is set
6. CLAUDE.md Entity Types section is accurate
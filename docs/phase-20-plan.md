# Phase 20: Adventure Builder & Runner

## Context

The current app is a **free-form linked wiki** — you create NPCs, Locations, Quests, etc. and connect them manually. This works as a reference tool but provides no guided workflow for *building* an adventure. There's no sense of structure, no step-by-step process, and the Story Arc (AdventureSite) is a single big Markdown blob — exactly the wall of text we want to avoid.

Pathfinder-style prewritten adventures are organized as **hierarchical structured documents**: Adventure → Acts → Scenes → Rooms. Each room is a self-contained card with read-aloud text, GM notes, creatures, and loot. This is the model we're moving toward.

**Goals:**
- AI-first draft: describe concept in one paragraph → AI generates entire adventure skeleton
- Structured data, not Markdown blobs — no walls of text
- At-table view: room navigation, reveal mechanism, combat integration, AI improv
- ICRPG-first but flexible (Hearts/effort or HP/AC per room creature)

---

## Feature Table

| Feature | Phase | Status | Notes |
|---------|-------|--------|-------|
| Data model (Adventure, Act, Scene, Room, Creature, Loot, Hazard) | 20a | Planned | 7 new models + 2 assoc tables |
| Flask migration | 20a | Planned | |
| `/adventures/` CRUD routes | 20a | Planned | list, detail, create, delete |
| `POST /api/ai/generate-adventure-draft` | 20a | Planned | AI-first single-prompt draft |
| Draft review UI (tree, inline editor, save) | 20a | Planned | adventure_builder.js |
| Adventures in navbar | 20a | Planned | base.html update |
| `GET /adventures/<id>/run` — Adventure Runner | 20b | Planned | Tablet-optimized |
| Left nav: act/scene/room tree (AJAX) | 20b | Planned | |
| Room card with read-aloud + GM notes | 20b | Planned | Card layout, no walls of text |
| Reveal mechanism (blur → reveal, visited tracking) | 20b | Planned | Flask session-scoped |
| Prev/next room navigation | 20b | Planned | |
| [+Add to Combat] on room creatures | 20c | Planned | Bridge to existing combat tracker |
| AI Improv modal (generate new room on-the-fly) | 20c | Planned | |
| NPC slide-in card in runner | 20c | Planned | |
| Consequences/suggestions AI buttons | 20c | Planned | Reuse existing session mode features |
| Mark room complete in nav | 20c | Planned | |

---

## Data Model

### New Models

```
Adventure
  id, campaign_id, name, tagline
  concept (original user prompt)
  synopsis, hook, premise
  system_hint: "icrpg" | "d20" | "generic"
  status: Draft / Ready / Active / Complete
  is_player_visible

AdventureAct
  id, adventure_id, number, title, description, sort_order

AdventureScene  (a dungeon, town, wilderness area, etc.)
  id, act_id, title, description, scene_type
  location_id (optional FK → existing Location model)
  sort_order

AdventureRoom  (keyed: A1, A2, B1, B2...)
  id, scene_id, key (e.g. "A1"), title
  read_aloud (player-facing, 2-3 sentences max)
  gm_notes (bullet-point text)
  is_revealed (boolean)
  sort_order

RoomCreature
  id, room_id, name
  ICRPG: hearts (int), effort_type (BASIC/WEAPON/MAGIC/ULTIMATE), special_move, timer_rounds
  d20: hp (int), ac (int), cr (str), actions (text)
  bestiary_entry_id (optional FK → BestiaryEntry)

RoomLoot
  id, room_id, name, description
  loot_def_id (optional FK → ICRPGLootDef)

RoomHazard
  id, room_id, name, description, dc_or_target, consequence
```

### New Association Tables
- `adventure_npc_link` — Adventure ↔ NPC (key NPCs)
- `adventure_faction_link` — Adventure ↔ Faction

### Relationships to Existing Entities
- AdventureSite (Story Arcs) remains untouched — legacy, not replaced
- AdventureScene optionally links to an existing Location (location_id FK)
- RoomCreature optionally links to an existing BestiaryEntry

---

## AI-First Build Workflow

### Step 1: Concept Input (`GET /adventures/create`)
Single text area: "Describe your adventure in a paragraph or two."
[Generate Adventure Draft →]

### Step 2: AI Draft (`POST /api/ai/generate-adventure-draft`)
AI receives concept + campaign world context + system_hint.
Returns structured JSON with title, tagline, synopsis, hook, acts (with scenes and rooms), key_npcs, factions.

Each room includes: key, title, read_aloud, gm_notes, creatures[], loot[].
Creature format adapts to system_hint (ICRPG: hearts/effort/special_move; d20: hp/ac/cr/actions).

### Step 3: Draft Review UI
Collapsible tree: Acts → Scenes → Rooms.
Click room → edit panel with all fields.
"Regenerate" and "Add" buttons per section.
[Save Adventure] → creates all DB records.

### Step 4: Create Linked Entities (optional post-save)
Offer to create NPC and Faction records from key_npcs/factions in the draft.

---

## Adventure Runner Layout

```
[LEFT: Navigator] | [CENTER: Room Card] | [RIGHT: Combat Panel]
```

Room card format (card sections, no paragraphs):
```
╔══════════════════════════════════╗
║ A1 · The Shattered Gate          ║
╠══════════════════════════════════╣
║ READ ALOUD          [REVEAL ▼]   ║
║ [blurred/hidden until revealed]  ║
╠══════════════════════════════════╣
║ GM NOTES                         ║
║ • Force: STR 15 / lockpick DC 12 ║
║ • Groaning sounds from beyond    ║
╠══════════════════════════════════╣
║ CREATURES                        ║
║ 💀 Skeleton Guard  ❤️ 1  [+Cbt]  ║
║ ⚡ Bone Rattle — stun 1 round    ║
╠══════════════════════════════════╣
║ LOOT                             ║
║ 🗝 Rusted Key — Opens door A3    ║
╠══════════════════════════════════╣
║ [← A0] [→ A2: Guard Room]        ║
╚══════════════════════════════════╝
```

---

## Files to Create / Modify

### Phase 20a
- `app/models.py` — add 7 new models + 2 association tables
- `migrations/versions/XXX_add_adventure_models.py` — Flask-Migrate
- `app/routes/adventures.py` — new Blueprint (list, detail, create, save, delete)
- `app/routes/ai.py` — add `generate-adventure-draft` endpoint
- `app/__init__.py` — register adventures Blueprint
- `app/templates/adventures/list.html`
- `app/templates/adventures/detail.html`
- `app/templates/adventures/create.html`
- `app/templates/adventures/draft_review.html`
- `app/static/js/adventure_builder.js`
- `app/templates/base.html` — add Adventures to navbar

### Phase 20b
- `app/routes/adventures.py` — add `/run` and `/rooms/<id>/reveal`
- `app/templates/adventures/runner.html`
- `app/static/js/adventure_runner.js`

### Phase 20c
- `app/routes/adventures.py` — add improv endpoint, room-complete toggle
- `app/routes/ai.py` — add improv-room endpoint
- `app/templates/adventures/runner.html` — improv modal, NPC panel
- `app/static/js/adventure_runner.js` — combat bridge

---

## Open Questions (resolve during build)

1. **Story Arcs** — keep in navbar alongside Adventures, or retire them?
2. **Reveal persistence** — Flask session (resets per visit) or permanent DB flag?
3. **Session linkage** — should running an adventure auto-create a Session record?

# The War Table — Canonical Data Model

## The Hierarchy

```
Campaign
├── Adventures (many per campaign)
│   ├── Act 1: Beginning
│   │   ├── Scene  (a physical area: dungeon, town, forest...)
│   │   │   ├── Location  ← UI label for "Room" (DB table: adventure_room)
│   │   │   └── Location
│   │   └── Scene
│   ├── Act 2: Middle
│   └── Act 3: End (or more acts as needed)
│
├── NPCs (campaign-wide; optionally scoped to an adventure)
├── Locations (campaign-wide world records; can be linked to adventure Locations)
├── Quests
│   ├── Campaign quests  (adventure_id = NULL; span multiple adventures)
│   └── Adventure quests (adventure_id = X; scoped to one adventure)
├── Items (campaign-wide; optionally scoped to an adventure)
├── Factions (campaign-wide; linked to adventures via M-to-M)
└── Sessions (campaign-scoped; link to an adventure when running one)
```

---

## Entity Definitions

### Campaign
The top-level container. All data belongs to exactly one campaign. No data bleeds between campaigns. Holds the game system, world name, and a stat template used by PCs.

### Adventure
A playable story module within the campaign. Has a beginning, middle, and end represented as Acts. Each adventure has a concept, synopsis, hook, premise, and system hint (ICRPG, d20, generic). An adventure can be in Draft, Active, or Complete status.

### Act
A story beat within an adventure (Act 1: Beginning, Act 2: Middle, Act 3: End, etc.). Contains one or more Scenes.

### Scene
A physical area within an Act — a dungeon level, a town district, a forest hex. Scenes have a type (dungeon, town, wilderness...) and an optional link to a campaign Location record.

### Location (UI) / AdventureRoom (DB: `adventure_room`)
The GM-runnable view of a specific place within a Scene during this adventure. Each location has:
- A **key** (shorthand reference like "A1", "BOSS")
- **Read-aloud text** revealed to players when they enter
- **GM notes** (bullet points, always visible to GM)
- **Creatures**, **Loot**, and **Hazards** as child records
- An optional **location_id** FK linking to a campaign Location record

> **Naming note:** The UI uses "Location" everywhere. Code, DB tables, Python variables, and URL patterns continue to use `room` / `adventure_room` to avoid a disruptive migration.

### Campaign Location (`locations`)
The canonical world record for a place. Lives forever in the campaign. An adventure Scene or adventure Location can optionally link to it.

### NPC
A named character in the world. Can be campaign-wide (`adventure_id = NULL`) or created specifically for one adventure (`adventure_id = X`). Can also be linked to an adventure via the M-to-M `adventure_npc_link` table to mark them as "featured" in that adventure without making them adventure-specific.

### PC (Player Character)
A player-controlled character. Linked to a campaign via `campaign_id`. Stats come from the campaign's stat template. Can be claimed by a user account.

### Quest
A story objective. Two scoping mechanisms:
- **Adventure quest**: `adventure_id = X` — scoped to one adventure, shown with a blue [Adventure] badge
- **Campaign quest**: `adventure_id = NULL`, linked to adventures via `adventure_quest_link` M-to-M — spans multiple adventures, shown with a gold [Campaign] badge

### Item
A physical object. Can be campaign-wide or adventure-specific via `adventure_id`.

### Faction
A group or organization. Always campaign-wide. Linked to adventures via `adventure_faction_link` M-to-M.

### Session
A record of a play session. Always campaign-scoped. Links to the adventure being run via `adventure_id`.

### Story Arc (`adventure_site`)
A long-form Markdown document used for worldbuilding, campaign-spanning story arcs, or pre-Phase-20 adventure sites. UI label: "Story Arcs". Not the same as Adventure — Story Arcs are free-form documents, Adventures are structured modules.

### Compendium
Custom rules reference entries, per campaign. Can be GM-only toggled.

### Encounter
A set of monsters, loot tables, and encounter details. Can link to a Session and an Adventure.

### Bestiary
Global monster entries (not campaign-scoped). Spawn as monster instances per campaign.

### Random Table
Weighted dice tables. Can be built-in (seeded from ICRPG/SRD data, `campaign_id = NULL`) or custom (created per campaign).

---

## Scope Rules

| Entity | Campaign-scoped | Adventure-scoped | How linked |
|---|---|---|---|
| NPC | `adventure_id = NULL` | `adventure_id = X` | Direct FK |
| NPC (featured) | campaign-wide | featured in adventure | `adventure_npc_link` M-to-M |
| Location (world) | campaign-wide | — | always campaign-wide |
| Scene | per-adventure | `act_id → adventure` | FK chain |
| Adventure Location | per-adventure | `scene_id → act → adventure` | FK chain; optional `location_id` → campaign Location |
| Quest | `adventure_id = NULL` | `adventure_id = X` | Direct FK |
| Quest (campaign-wide) | `adventure_id = NULL` | linked to adventures | `adventure_quest_link` M-to-M |
| Item | `adventure_id = NULL` | `adventure_id = X` | Direct FK |
| Faction | campaign-only | linked to adventures | `adventure_faction_link` M-to-M |
| Session | campaign-scoped | `adventure_id = X` | Direct FK |

---

## M-to-M Association Tables

| Table | Left | Right | Purpose |
|---|---|---|---|
| `adventure_npc_link` | `adventure.id` | `npcs.id` | Featured NPCs per adventure |
| `adventure_faction_link` | `adventure.id` | `factions.id` | Factions per adventure |
| `adventure_quest_link` | `adventure.id` | `quests.id` | Campaign quests per adventure |

---

## Naming Conventions

| Concept | UI label | DB table / column | Python class |
|---|---|---|---|
| Adventure location / room | Location | `adventure_room` | `AdventureRoom` |
| Session in code | Session | `sessions` | `Session` aliased as `GameSession` |
| Story arc document | Story Arc | `adventure_site` | `AdventureSite` |
| Campaign Location | Location | `locations` | `Location` |

---

## Quest Scope Badges (Runner / Detail Page)

- Blue **[Adventure]** badge: `quest.adventure_id == adventure.id` — this quest was created for this specific adventure
- Gold **[Campaign]** badge: `quest.adventure_id is None`, linked via `adventure_quest_link` — this quest spans multiple adventures

---

## NPC Dual-Link Clarification

Two ways an NPC can be associated with an adventure:

1. **`npc.adventure_id = X`** — The NPC was *created for* this adventure (adventure-specific). They live and die with the adventure.
2. **`adventure_npc_link`** — An existing campaign-wide NPC is *featured in* this adventure (Key NPC). They exist independently of the adventure and may appear in other adventures too.

The adventure detail Entities tab labels these as "Adventure-Specific NPCs" and "Featured NPCs from Campaign" respectively.

---

## Location Linking Chain

```
Campaign Location (locations.id)
  ↑ optional FK (location_id)
Adventure Location / Room (adventure_room)
  ↑ FK (scene_id)
Scene (adventure_scene)
  ↑ optional FK (location_id)  ← scene can also link to a campaign Location
Adventure Scene
  ↑ FK (act_id)
Act (adventure_act)
  ↑ FK (adventure_id)
Adventure
  ↑ FK (campaign_id)
Campaign
```

When an adventure Location is linked to a campaign Location, the location card in the runner shows the campaign Location name as a clickable link.

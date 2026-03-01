# The War Table — Architecture & Feature Overview

The War Table is a self-hosted, browser-based campaign management tool for tabletop RPG Game Masters. It runs as a Flask/SQLite web application inside a Docker container on a home server (Unraid), accessed via browser from any device on the local network or through a Cloudflare tunnel. Its core purpose is to give a GM one place to write, organize, and navigate all campaign content — world-building entities, session prep, live-session dashboards, and encounter tracking — with everything cross-linked and clickable so that the right information is always one tap away at the game table.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9 + Flask |
| Database | SQLite via Flask-SQLAlchemy |
| Migrations | Flask-Migrate (Alembic) |
| Templating | Jinja2 |
| Frontend | Bootstrap 5 (dark theme), vanilla JS |
| Auth | Flask-Login (session-based) |
| CSRF | Flask-WTF |
| AI | Claude API (Anthropic) — Smart Fill and content generation |
| Image Gen | Stable Diffusion (local, optional) |
| Hosting | Docker on Unraid; public access via Cloudflare tunnel |

---

## Project Structure

```
gm-wiki/
├── app/
│   ├── __init__.py              # App factory — create_app(), registers all blueprints
│   ├── models.py                # All SQLAlchemy models (single file)
│   ├── shortcode.py             # #type[Name] shortcode processing system
│   ├── ai_provider.py           # Claude AI integration
│   ├── sd_provider.py           # Stable Diffusion image generation
│   ├── obsidian_parser.py       # Obsidian vault file importer
│   ├── routes/                  # One Blueprint per feature area (~30 files)
│   │   ├── main.py              # Homepage, campaign switching
│   │   ├── auth.py              # Login, signup, logout
│   │   ├── admin.py             # User management (admin only)
│   │   ├── campaigns.py         # Campaign CRUD + stat templates
│   │   ├── adventure_sites.py   # Adventure Site CRUD + replace-text API
│   │   ├── npcs.py
│   │   ├── locations.py
│   │   ├── quests.py
│   │   ├── items.py
│   │   ├── sessions.py
│   │   ├── compendium.py
│   │   ├── factions.py
│   │   ├── pcs.py               # Player Characters
│   │   ├── encounters.py
│   │   ├── bestiary.py
│   │   ├── monsters.py          # Monster instances (spawned from bestiary)
│   │   ├── tables.py            # Random tables
│   │   ├── tags.py
│   │   ├── session_mode.py      # Live session dashboard
│   │   ├── combat.py            # Combat tracker
│   │   ├── wiki.py              # Player-facing read-only wiki
│   │   ├── ai.py                # AI Smart Fill routes
│   │   ├── quick_create.py      # JSON API: create any entity by name
│   │   ├── global_search.py
│   │   ├── entity_search.py
│   │   ├── settings.py
│   │   ├── obsidian_import.py
│   │   ├── srd_import.py
│   │   └── bestiary_import.py
│   ├── templates/
│   │   ├── base.html            # Shared layout — navbar, footer, Bootstrap/JS includes
│   │   ├── adventure_sites/     # list.html, form.html, detail.html
│   │   ├── npcs/ locations/ quests/ items/ sessions/ ...
│   │   └── wiki/                # Player-facing templates
│   └── static/
│       ├── css/custom.css
│       ├── js/
│       │   ├── quick_create.js          # Inline entity creation (global)
│       │   ├── entity_from_selection.js # Text-selection entity creation (Adventure Sites only)
│       │   ├── global_search.js
│       │   ├── dice_roller.js
│       │   ├── shortcode.js
│       │   └── table_sort.js
│       └── uploads/             # Uploaded images (portraits, maps, item art)
├── migrations/versions/         # Alembic migration files (one per schema change)
├── docs/                        # Phase plans + this file
├── instance/gm_wiki.db          # SQLite database (not in git)
├── config.py
├── run.py                       # Entry point — always start with: python3 run.py
├── Dockerfile
├── docker-compose.yml
├── docker-entrypoint.sh         # Runs `flask db upgrade` on container start
└── update.sh                    # Unraid deploy script: git pull + rebuild + restart
```

---

## Multi-Tenancy Model

- One app instance serves multiple **Users**
- Each User owns one or more **Campaigns**
- Almost all data is scoped to a `campaign_id` — NPCs, Locations, Sessions, etc. from Campaign A are completely invisible to Campaign B
- The active campaign is stored in `flask.session['active_campaign_id']` and set via a campaign-switcher dropdown in the navbar
- **Exceptions to campaign scoping:**
  - `BestiaryEntry` — global monster library shared across all campaigns (campaign-scoped `MonsterInstance` records are spawned from it)
  - `RandomTable` — tables with `campaign_id=NULL` are built-in global tables visible to all campaigns; custom tables are campaign-scoped
  - `AppSetting` — single key-value store, app-wide (AI provider URLs, keys, etc.)

---

## Entity Types and Data Model

### Campaign
The top-level container. Everything belongs to a campaign.

| Field | Notes |
|-------|-------|
| name, system, status | system is free text ("D&D 5e", "ICRPG", etc.) |
| description | Overview of the campaign |
| image_style_prompt | Prepended to all Stable Diffusion prompts for this campaign |
| ai_world_context | Injected into AI Generate Entry system prompts |

---

### AdventureSite *(added Phase 8+)*
A prepared scenario document — dungeon, town, region, or any self-contained area designed to be run at the table. The key design insight: instead of scattering one floor's content across 5 Locations + 5 Encounters + 1 NPC boss, the GM writes everything in one structured Markdown document. `##` headings define zones; the detail view auto-generates a Table of Contents and section checkboxes from those headings for live-session navigation.

| Field | Notes |
|-------|-------|
| name | Required |
| subtitle | One-line tagline shown on the list page |
| status | Planned / Active / Completed |
| estimated_sessions | Integer — how many sessions expected |
| content | Full Markdown body (zones, encounters, boss stats, loot, GM notes) |
| sort_order | Integer for manual ordering on the list page |

**Relationships:**
- `campaign` (many-to-one)
- `tags` (many-to-many via `adventure_site_tags`)
- `sessions` (many-to-many via `adventure_site_session`)

**Detail view features:**
- Auto-generated ToC from `##` and `###` headings (vanilla JS, IntersectionObserver highlights current section)
- Run State sidebar: a generic counter widget (label + +/- buttons) and per-section checkboxes, all persisted in `localStorage` keyed by site ID — no server round-trips, survives page refresh
- Linked Sessions panel in sidebar

---

### NPC
A named character in the world. Separate from Player Characters.

| Field | Notes |
|-------|-------|
| name, role, status | status: alive/dead/unknown/missing |
| physical_description, personality | |
| secrets | **GM-only — never shown in player wiki** |
| notes | General notes, supports Markdown |
| portrait_filename | Uploaded image |
| home_location_id | FK → Location (one-to-one "home base") |
| faction_id | FK → Faction |
| is_player_visible | Controls wiki visibility |

**Relationships:**
- `home_location` (many-to-one)
- `connected_locations` (many-to-many via `npc_location_link` — locations the NPC frequents)
- `faction_rel` (many-to-one)
- `tags` (many-to-many)
- `quests` (many-to-many, backref from Quest)
- `sessions` (many-to-many, backref from Session)
- `items_owned` (one-to-many, backref from Item)

---

### PlayerCharacter (PC)
A player's character. Distinct from NPCs — different fields, separate visibility rules, used by combat tracker and session mode.

| Field | Notes |
|-------|-------|
| character_name, player_name | |
| level_or_rank, class_or_role, race_or_ancestry | All free text — system-agnostic |
| description, backstory, gm_hooks, notes | |
| status | active/inactive/retired/dead/npc |
| portrait_filename | |
| home_location_id | FK → Location |
| user_id | FK → User (if a player has claimed this character) |

Stats are stored in a separate `PlayerCharacterStat` table linked to `CampaignStatTemplate` rows. The template defines what stats the campaign tracks (e.g. "HP", "Armor", "STR") — this keeps the system agnostic.

---

### Location
A place in the world. Supports nesting (region → city → district).

| Field | Notes |
|-------|-------|
| name, type | type is free text |
| description | Player-visible |
| gm_notes | **GM-only** |
| notes | General Markdown notes |
| map_filename | Uploaded image |
| parent_location_id | Self-referencing FK for nesting |
| faction_id | Controlling faction |
| is_player_visible | Wiki visibility |

**Relationships:**
- `parent_location` / `child_locations` (self-referencing tree)
- `connected_locations` (many-to-many self-join via `location_connection` — roads, passages, etc.)
- `npcs_living_here` (backref from NPC.home_location)
- `notable_npcs` (backref from NPC.connected_locations)
- `quests`, `sessions`, `items_found_here` (backrefs)
- `tags` (many-to-many)

---

### Quest
A story objective or mission.

| Field | Notes |
|-------|-------|
| name, status | status: active/completed/failed/on_hold |
| hook | How the party got involved |
| description | Full quest description |
| outcome | Fill in after resolution |
| gm_notes | **GM-only** |
| faction_id | Sponsoring faction |
| is_player_visible | Wiki visibility |

**Relationships:**
- `involved_npcs` (many-to-many)
- `involved_locations` (many-to-many)
- `tags`, `sessions` (backrefs)

---

### Item
A named object — weapon, tool, consumable, artifact, etc.

| Field | Notes |
|-------|-------|
| name, type, rarity | rarity: common/uncommon/rare/very rare/legendary/unique |
| description | Player-visible |
| gm_notes | **GM-only** |
| image_filename | |
| owner_npc_id | FK → NPC (null = party owns it) |
| origin_location_id | FK → Location (null = unknown) |
| is_player_visible | Wiki visibility |

---

### Session
A log of one play session, plus prep notes for the next one.

| Field | Notes |
|-------|-------|
| number, title, date_played | |
| prep_notes | Pre-session planning (shown in Session Mode dashboard) |
| summary | Post-session recap |
| gm_notes | **GM-only** |
| pinned_npc_ids | JSON array — NPCs pinned to the Session Mode quick panel |
| active_location_id | FK → Location (current scene location) |
| is_player_visible | Wiki visibility |

**Relationships:**
- `npcs_featured` (many-to-many)
- `locations_visited` (many-to-many)
- `items_mentioned` (many-to-many)
- `quests_touched` (many-to-many)
- `adventure_sites` (many-to-many, backref from AdventureSite)
- `attendances` → `PlayerCharacter` (via SessionAttendance join table)
- `encounters` (one-to-many)
- `monsters_encountered` (many-to-many via MonsterInstance)
- `tags` (many-to-many)

---

### Faction
A named organization, guild, or group.

| Field | Notes |
|-------|-------|
| name, description, disposition | disposition: friendly/neutral/hostile/unknown |
| gm_notes | **GM-only** |

Backrefs: `npcs`, `locations`, `quests`

---

### CompendiumEntry
A custom rules reference page, per campaign.

| Field | Notes |
|-------|-------|
| title, category | category is free text |
| content | Markdown body |
| is_gm_only | Hides from player wiki |

---

### Tag
Shared tagging system. Tags are campaign-scoped (unique per name + campaign_id). Used by: NPC, Location, Quest, Item, Session, AdventureSite.

---

### BestiaryEntry + MonsterInstance
Two-layer monster system:
- `BestiaryEntry` — global template, not campaign-scoped. Stat block in Markdown. Tags stored as comma-separated text (not the Tag model, since it's global).
- `MonsterInstance` — a specific creature spawned from a BestiaryEntry into a campaign. Has a name (e.g. "Goblin 1"), status (alive/dead/fled), and can be promoted to a full NPC if the creature becomes a named character.

---

### Encounter
A pre-planned encounter tied to a session.

| Field | Notes |
|-------|-------|
| name, encounter_type | type: combat/loot/social/trap/other |
| status | planned/used/skipped |
| description, gm_notes | |
| loot_table_id | FK → RandomTable |
| session_id | FK → Session |

Contains `EncounterMonster` child rows (one per creature type + count).

---

### RandomTable + TableRow
Rollable tables. `campaign_id=NULL` = built-in global table. Custom tables belong to a campaign. Rows have a `weight` field for weighted probability. One-click rolling in the UI.

---

### AppSetting
Key-value store for app-wide configuration (AI provider, SD server URL, API keys). Read/written from the Settings page — no `.env` editing required.

---

### EntityMention
Auto-populated cross-reference table. When a shortcode is processed on save (e.g. `#npc[The Foreman]` in an Adventure Site), a row is written: `(source_type='site', source_id=5, target_type='npc', target_id=12)`. This powers the "Referenced by" section on entity detail pages — clicking on The Foreman's NPC page shows every Adventure Site, Quest, Session, etc. that links to him.

---

## The Shortcode System

Shortcodes are inline `#type[Name]` markers in any text field that supports Markdown. On save, `app/shortcode.py` scans the content, replaces each shortcode with an HTML anchor tag, and writes an `EntityMention` row for each match.

**Supported shortcode types:**

| Shortcode | Links to | Route |
|-----------|----------|-------|
| `#npc[Name]` | NPC detail page | `npcs.npc_detail` |
| `#loc[Name]` | Location detail page | `locations.location_detail` |
| `#quest[Name]` | Quest detail page | `quests.quest_detail` |
| `#item[Name]` | Item detail page | `items.item_detail` |
| `#session[Name]` | Session detail page | `sessions.session_detail` |
| `#compendium[Name]` | Compendium entry | `compendium.entry_detail` |
| `#site[Name]` | Adventure Site detail | `adventure_sites.site_detail` |

`TYPE_CONFIG` in `shortcode.py` maps each type key to its model class, name field, route name, and route parameter. When a shortcode is encountered, the system queries the DB by name within the campaign, generates the link, and records the mention.

On edit, `clear_mentions(source_type, source_id)` deletes all prior mention rows for that entity, then `process_shortcodes()` re-scans and re-writes them fresh.

---

## The Quick Create API

`POST /api/quick-create/<entity_type>` — JSON endpoint for creating any entity by name without leaving the current page.

**Request body:**
```json
{ "name": "The Foreman", "description": "Hulking spliced overseer" }
```

**Response:**
```json
{ "id": 42, "name": "The Foreman", "shortcode": "#npc[The Foreman]" }
```

- `description` is optional — stored in the appropriate field per entity type (NPC → `role`, Location → `description`, Quest/Item → `notes`)
- If an entity with that name already exists in the campaign, returns the existing record (idempotent)
- `shortcode` is only included for NPC, Location, Quest, and Item (the four types that have shortcode links)
- Used by two client-side systems: the global Quick Create button (navbar) and the Adventure Site text-selection tool

**Shortcode prefix mapping:**
```
npc → #npc[...]
location → #loc[...]
quest → #quest[...]
item → #item[...]
```

---

## Text-Selection Entity Creation (Adventure Sites)

Loaded only on Adventure Site pages (`entity_from_selection.js`). Lets the GM select any text in the adventure content and instantly create an entity from it.

### How it works

**Edit view (textarea):**
1. GM selects text in the `#content` textarea
2. A floating toolbar appears above the selection: `NPC · Location · Quest · Item`
3. GM clicks a type → Bootstrap modal opens with the selected text pre-filled in the Name field, plus a secondary field (Role / Description / Notes)
4. GM fills in the fields and clicks:
   - **Create & Link** → POSTs to `/api/quick-create/<type>`, gets back a shortcode, replaces the selected textarea range (`selectionStart`→`selectionEnd`) with the shortcode, dispatches an `input` event
   - **Just Create** → Creates the entity, shows a Bootstrap toast with the shortcode to copy manually

**Detail/Run view (rendered HTML):**
1. GM selects rendered text in `#site-content`
2. Same floating toolbar, same modal
3. On **Create & Link** → after creating the entity, POSTs to `POST /sites/<id>/replace-text` with `{ "find": "The Foreman", "replace": "#npc[The Foreman]" }`. Server does a first-occurrence string replace on `site.content`, commits, returns `{ "success": true }` → page reloads showing the new link
4. If the text isn't found exactly (e.g. whitespace difference), shows a toast with the shortcode to copy manually

### Implementation files

| File | Role |
|------|------|
| `app/static/js/entity_from_selection.js` | All client logic: toolbar, modal, edit-view replacement, detail-view replace-text call, toasts |
| `app/routes/adventure_sites.py` | `POST /sites/<id>/replace-text` endpoint |
| `app/routes/quick_create.py` | Extended with `description` field and `shortcode` in response |
| `app/templates/adventure_sites/detail.html` | `<div id="efs-context" data-site-id="..." data-mode="detail">` + script in `{% block scripts %}` |
| `app/templates/adventure_sites/form.html` | Same context div with `data-mode="edit"`, script only on edit (not create-new) |

The JS reads the context div's `data-mode` attribute to know whether it's in edit or detail mode, and behaves differently in each case.

---

## The Player-Facing Wiki

A completely separate read-only view (`/wiki/<campaign_id>/...`) for players. Enforces three visibility rules:

1. Any entity with `is_player_visible = False` is completely hidden
2. `NPC.secrets` and `NPC.gm_notes` are **never** rendered in wiki views, even if the NPC is visible
3. `CompendiumEntry.is_gm_only` entries are hidden

The wiki is accessible without login. It uses separate templates under `app/templates/wiki/`.

---

## Session Mode

A live-session dashboard (`/session-mode/<session_id>`) designed for the GM at the table. Shows:
- Prep notes for the session (Markdown rendered)
- Pinned NPCs with quick notes
- Active location
- NPC Quick Chat — type a message, get an in-character AI response as that NPC
- "Go Live" / status indicators

---

## AI Integration

Two modes, configurable per feature in Settings:

1. **Smart Fill** — given an entity's name and any existing fields, Claude fills in the remaining fields (personality, description, notes, etc.) using the campaign's `ai_world_context` as a system prompt
2. **Generate Entry** — for Compendium entries, generates full rules text
3. **NPC Quick Chat** (Session Mode) — given an NPC's profile and a GM message, returns an in-character response

Provider, model, and API key are stored in `AppSetting` and editable from the Settings page. Different features can use different providers/models.

---

## Database Migration Pattern

Uses Flask-Migrate (Alembic). Never uses `db.create_all()` in production.

- Migration files live in `migrations/versions/`
- Each file has a unique `revision` ID (string) and a `down_revision` pointer forming a linked list
- **Critical:** revision IDs must be unique across all files — collision causes "Multiple head revisions" error
- Migrations run automatically on Docker container start via `docker-entrypoint.sh`
- To add a new model: write the model in `models.py`, write a migration file manually (or generate with `FLASK_APP=run.py python3 -m flask db migrate`), then run `flask db upgrade`

---

## Entity Relationship Summary (Web, not Tree)

```
Campaign
│
├── AdventureSite ←──────────────── Session (many-to-many)
│     └── [content: Markdown body]
│           └── shortcodes link to any entity below
│
├── Session ←→ NPC, Location, Item, Quest (many-to-many each)
│         ←→ PlayerCharacter (via SessionAttendance)
│         ←→ Encounter → EncounterMonster → BestiaryEntry
│         ←→ MonsterInstance
│
├── NPC ←→ Location (home + connected, many-to-many)
│       ←→ Faction
│       ←→ Quest (many-to-many)
│       owns Items
│
├── Location (nestable: parent → children)
│         ←→ Location (connected, many-to-many self-join)
│         ←→ Faction
│
├── Quest ←→ NPC, Location, Faction (many-to-many)
│
├── Item → NPC (owner), Location (origin)
│
├── Faction ← NPC, Location, Quest (many reference one)
│
├── BestiaryEntry (global) → MonsterInstance (campaign-scoped)
│                                     └── can promote → NPC
│
├── RandomTable (global or campaign) → TableRow
│                    ↑ used by Encounter.loot_table
│
├── Tag (campaign-scoped, shared pool)
│     └── used by NPC, Location, Quest, Item, Session, AdventureSite
│
├── CompendiumEntry
├── PlayerCharacter → PlayerCharacterStat → CampaignStatTemplate
├── EntityMention (auto-generated shortcode back-links)
└── AppSetting (app-wide key-value config)
```

---

## GM Workflow (Intended Use)

**Prep phase (before a session):**
1. Create or open an **Adventure Site** — write the whole scenario in one Markdown document using `##` zone headings
2. As you write, select entity names and use the text-selection toolbar to create **NPCs**, **Quests**, and **Items** in-place — the selected text is replaced with a shortcode link automatically
3. Link the Adventure Site to an upcoming **Session**

**At the table (during a session):**
1. Open the Adventure Site **detail view** — use the sticky ToC to jump between zones
2. Use **Run State** sidebar: tick section checkboxes as zones are cleared; use the counter for timers/rounds
3. Switch to **Session Mode** for the NPC quick panel, active location tracking, and NPC Quick Chat
4. Open the **Combat Tracker** when a fight starts

**Post-session:**
1. Fill in the **Session summary**
2. Update NPC statuses (alive → dead), quest statuses, item ownership
3. Anything the players discovered can be marked `is_player_visible = True` to appear in the player wiki

---

## Deployment

- **Local dev:** `python3 run.py` from the `gm-wiki/` directory (port 5001)
- **Production:** Docker container on Unraid, Cloudflare tunnel at `wartable.overturffamily.com`
- **Update:** SSH into Unraid → `bash /mnt/user/appdata/gm-wiki/update.sh` (pulls latest git, rebuilds image, restarts container, runs migrations automatically)
- **Persistent volumes:** `./instance` (SQLite DB) and `./uploads` (images) survive container rebuilds

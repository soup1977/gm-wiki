# Phase 3 Plan — Quests, Sessions, Items, and Compendium

## Goal

Add the four remaining entity types: Quests, Items, Compendium entries, and Sessions. Each follows the same pattern established in Phase 2: model → migration → routes → templates → linking. Sessions come last because they link to everything else.

When this phase is done, every major entity type in the app exists and is cross-linked.

---

## Database Models

All models go in `app/models.py`. Existing models stay as-is.

### Quest Model

Quests are linked to involved NPCs and Locations via many-to-many tables.

```python
# Association tables — defined BEFORE the Quest class
quest_npc_link = db.Table('quest_npc_link',
    db.Column('quest_id', db.Integer, db.ForeignKey('quests.id'), primary_key=True),
    db.Column('npc_id', db.Integer, db.ForeignKey('npcs.id'), primary_key=True)
)

quest_location_link = db.Table('quest_location_link',
    db.Column('quest_id', db.Integer, db.ForeignKey('quests.id'), primary_key=True),
    db.Column('location_id', db.Integer, db.ForeignKey('locations.id'), primary_key=True)
)


class Quest(db.Model):
    __tablename__ = 'quests'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), default='active')  # active / completed / failed / on_hold
    hook = db.Column(db.Text)          # How the party got involved
    description = db.Column(db.Text)   # Full quest description
    outcome = db.Column(db.Text)       # What happened (fill in when resolved)
    gm_notes = db.Column(db.Text)      # GM-only, never shown to players
    is_player_visible = db.Column(db.Boolean, default=False)  # Phase 6

    campaign = db.relationship('Campaign', backref='quests')
    involved_npcs = db.relationship('NPC', secondary=quest_npc_link, backref='quests')
    involved_locations = db.relationship('Location', secondary=quest_location_link, backref='quests')
```

**Status choices:** `['active', 'completed', 'failed', 'on_hold']`

---

### Item Model

Items have a single owner (an NPC, or `None` if party-owned) and an origin location. No many-to-many needed — just foreign keys.

```python
class Item(db.Model):
    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(100))      # weapon / armor / consumable / misc (free text)
    rarity = db.Column(db.String(50))     # common / uncommon / rare / very rare / legendary
    description = db.Column(db.Text)
    gm_notes = db.Column(db.Text)         # GM-only, never shown to players
    is_player_visible = db.Column(db.Boolean, default=False)  # Phase 6

    owner_npc_id = db.Column(db.Integer, db.ForeignKey('npcs.id'), nullable=True)
    origin_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)

    campaign = db.relationship('Campaign', backref='items')
    owner_npc = db.relationship('NPC', backref='items_owned', foreign_keys=[owner_npc_id])
    origin_location = db.relationship('Location', backref='items_found_here', foreign_keys=[origin_location_id])
```

**Rarity choices:** `['common', 'uncommon', 'rare', 'very rare', 'legendary', 'unique']`

---

### CompendiumEntry Model

A simple per-campaign reference list. Each entry is a titled block of text (rules, lore, house rules, etc.) with an optional category and a GM-only toggle.

```python
class CompendiumEntry(db.Model):
    __tablename__ = 'compendium_entries'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))   # free text: "Combat", "Magic", "House Rules", etc.
    content = db.Column(db.Text)
    is_gm_only = db.Column(db.Boolean, default=False)

    campaign = db.relationship('Campaign', backref='compendium_entries')
```

> Note: `is_gm_only` is used here immediately (unlike `is_player_visible` on other models). Compendium entries marked GM-only are hidden in the player wiki view in Phase 6.

---

### Session Model

Sessions are the most connected entity — they link to NPCs, Locations, Items, and Quests via four separate many-to-many tables.

```python
# Association tables — defined BEFORE the Session class
session_npc_link = db.Table('session_npc_link',
    db.Column('session_id', db.Integer, db.ForeignKey('sessions.id'), primary_key=True),
    db.Column('npc_id', db.Integer, db.ForeignKey('npcs.id'), primary_key=True)
)

session_location_link = db.Table('session_location_link',
    db.Column('session_id', db.Integer, db.ForeignKey('sessions.id'), primary_key=True),
    db.Column('location_id', db.Integer, db.ForeignKey('locations.id'), primary_key=True)
)

session_item_link = db.Table('session_item_link',
    db.Column('session_id', db.Integer, db.ForeignKey('sessions.id'), primary_key=True),
    db.Column('item_id', db.Integer, db.ForeignKey('items.id'), primary_key=True)
)

session_quest_link = db.Table('session_quest_link',
    db.Column('session_id', db.Integer, db.ForeignKey('sessions.id'), primary_key=True),
    db.Column('quest_id', db.Integer, db.ForeignKey('quests.id'), primary_key=True)
)


class Session(db.Model):
    __tablename__ = 'sessions'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    number = db.Column(db.Integer)           # e.g. 1, 2, 3...
    title = db.Column(db.String(200))        # optional short title
    date_played = db.Column(db.Date)
    summary = db.Column(db.Text)             # What happened this session
    gm_notes = db.Column(db.Text)            # GM-only notes
    is_player_visible = db.Column(db.Boolean, default=False)  # Phase 6

    campaign = db.relationship('Campaign', backref='sessions')
    npcs_featured = db.relationship('NPC', secondary=session_npc_link, backref='sessions')
    locations_visited = db.relationship('Location', secondary=session_location_link, backref='sessions')
    items_mentioned = db.relationship('Item', secondary=session_item_link, backref='sessions')
    quests_touched = db.relationship('Quest', secondary=session_quest_link, backref='sessions')
```

---

## Routes

Create four new blueprint files in `app/routes/`. Register each in `app/__init__.py`.

### Quest Routes (`app/routes/quests.py`)

| Route | Method | What It Does |
|-------|--------|--------------|
| `/quests` | GET | List all quests in active campaign. Show name, status. |
| `/quests/new` | GET | Show create form. |
| `/quests/new` | POST | Save new quest. Redirect to detail page. |
| `/quests/<id>` | GET | Show quest detail with all fields and linked NPCs/locations. |
| `/quests/<id>/edit` | GET | Show edit form pre-filled. |
| `/quests/<id>/edit` | POST | Save changes. Redirect to detail page. |
| `/quests/<id>/delete` | POST | Delete quest. Redirect to quest list. |

### Item Routes (`app/routes/items.py`)

| Route | Method | What It Does |
|-------|--------|--------------|
| `/items` | GET | List all items in active campaign. Show name, type, rarity, owner. |
| `/items/new` | GET | Show create form. |
| `/items/new` | POST | Save new item. Redirect to detail page. |
| `/items/<id>` | GET | Show item detail with all fields, owner NPC (linked), origin location (linked). |
| `/items/<id>/edit` | GET | Show edit form pre-filled. |
| `/items/<id>/edit` | POST | Save changes. Redirect to detail page. |
| `/items/<id>/delete` | POST | Delete item. Redirect to item list. |

### Compendium Routes (`app/routes/compendium.py`)

| Route | Method | What It Does |
|-------|--------|--------------|
| `/compendium` | GET | List all entries in active campaign. Show title, category, GM-only badge. |
| `/compendium/new` | GET | Show create form. |
| `/compendium/new` | POST | Save new entry. Redirect to detail page. |
| `/compendium/<id>` | GET | Show full entry content. |
| `/compendium/<id>/edit` | GET | Show edit form pre-filled. |
| `/compendium/<id>/edit` | POST | Save changes. Redirect to detail page. |
| `/compendium/<id>/delete` | POST | Delete entry. Redirect to list. |

### Session Routes (`app/routes/sessions.py`)

| Route | Method | What It Does |
|-------|--------|--------------|
| `/sessions` | GET | List all sessions in active campaign. Show number, title, date. Most recent first. |
| `/sessions/new` | GET | Show create form. |
| `/sessions/new` | POST | Save new session. Redirect to detail page. |
| `/sessions/<id>` | GET | Show session detail with summary and all linked entities. |
| `/sessions/<id>/edit` | GET | Show edit form pre-filled. |
| `/sessions/<id>/edit` | POST | Save changes. Redirect to detail page. |
| `/sessions/<id>/delete` | POST | Delete session. Redirect to session list. |

---

## Templates

Create four new folders in `app/templates/`. Each needs `list.html`, `detail.html`, and `form.html`.

### Quest Templates

- **`quests/list.html`** — Table with columns: Name (linked), Status (badge), Actions. "New Quest" button at top.
- **`quests/detail.html`** — All fields. "Involved NPCs" and "Involved Locations" as clickable links. Edit/Delete buttons. Breadcrumb: Quests > Name.
- **`quests/form.html`** — Fields: Name (required), Status (dropdown), Hook (textarea), Description (textarea), Outcome (textarea), GM Notes (textarea, labeled "GM Only"), Involved NPCs (multi-select), Involved Locations (multi-select).

### Item Templates

- **`items/list.html`** — Table with columns: Name (linked), Type, Rarity (badge), Owner. "New Item" button at top.
- **`items/detail.html`** — All fields. Owner NPC and Origin Location as clickable links. Edit/Delete buttons. Breadcrumb: Items > Name.
- **`items/form.html`** — Fields: Name (required), Type (text), Rarity (dropdown), Description (textarea), GM Notes (textarea, "GM Only"), Owner NPC (dropdown — blank = party), Origin Location (dropdown — blank = unknown).

### Compendium Templates

- **`compendium/list.html`** — Table with columns: Title (linked), Category, GM Only (badge if true). "New Entry" button at top.
- **`compendium/detail.html`** — Full entry: title, category, content (plain text for now, Markdown in Phase 4). GM Only badge if set. Edit/Delete buttons. Breadcrumb: Compendium > Title.
- **`compendium/form.html`** — Fields: Title (required), Category (text), Content (textarea), GM Only (checkbox).

### Session Templates

- **`sessions/list.html`** — Table with columns: Number, Title (linked), Date Played. Newest first. "New Session" button at top.
- **`sessions/detail.html`** — All fields. Four linked-entity sections: Featured NPCs, Locations Visited, Items Mentioned, Quests Touched — all as clickable links. Edit/Delete buttons. Breadcrumb: Sessions > #N — Title.
- **`sessions/form.html`** — Fields: Number (number input), Title (text), Date Played (date input), Summary (textarea), GM Notes (textarea, "GM Only"), Featured NPCs (multi-select), Locations Visited (multi-select), Items Mentioned (multi-select), Quests Touched (multi-select).

### Navigation Update

Update `base.html` to wire up the four placeholder nav links that are already there (Quests, Sessions, Items, Compendium). They currently point to `#`.

---

## Build Order

Follow this order so each piece is testable before moving on.

### Step 1: Quest model + CRUD
- Add `quest_npc_link`, `quest_location_link`, and `Quest` to `models.py`
- Run migration: `flask db migrate -m "Add Quest model and link tables"` then `flask db upgrade`
- Create `app/routes/quests.py` with all routes
- Register the `quests` blueprint in `app/__init__.py`
- Create all three Quest templates
- Test: create, view, edit, delete a quest; link NPCs and locations; verify they show on the quest page
- **Branch:** `feature/quest-crud`
- **Commits:**
  - `"Add Quest model and migration"`
  - `"Add Quest routes and templates"`

### Step 2: Item model + CRUD
- Add `Item` to `models.py` (no association tables needed — just FKs)
- Run migration: `flask db migrate -m "Add Item model"` then `flask db upgrade`
- Create `app/routes/items.py` with all routes
- Register the `items` blueprint in `app/__init__.py`
- Create all three Item templates
- Test: create an item, assign an owner NPC and origin location, verify links work
- **Branch:** `feature/item-crud`
- **Commits:**
  - `"Add Item model and migration"`
  - `"Add Item routes and templates"`

### Step 3: Compendium model + CRUD
- Add `CompendiumEntry` to `models.py`
- Run migration: `flask db migrate -m "Add CompendiumEntry model"` then `flask db upgrade`
- Create `app/routes/compendium.py` with all routes
- Register the `compendium` blueprint in `app/__init__.py`
- Create all three Compendium templates
- Test: create entries, toggle GM Only, verify it displays correctly
- **Branch:** `feature/compendium-crud`
- **Commits:**
  - `"Add CompendiumEntry model and migration"`
  - `"Add Compendium routes and templates"`

### Step 4: Session model + CRUD
- Add all four session link tables and the `Session` model to `models.py`
- Run migration: `flask db migrate -m "Add Session model and link tables"` then `flask db upgrade`
- Create `app/routes/sessions.py` with all routes
- Register the `sessions` blueprint in `app/__init__.py`
- Create all three Session templates
- Test: create a session, link NPCs/locations/items/quests, verify all appear on the session page; verify sessions appear on each linked entity's detail page (via backref)
- **Branch:** `feature/session-crud`
- **Commits:**
  - `"Add Session model and migration"`
  - `"Add Session routes and templates"`

### Step 5: Nav wiring + polish
- Update `base.html` to replace the `#` hrefs for Quests, Sessions, Items, Compendium with real `url_for()` calls
- Run the full cross-link test: session → click quest → click NPC → click home location → verify all paths work
- **Branch:** `feature/phase3-nav-polish`
- **Commit:** `"Wire up nav links for Phase 3 entities"`

---

## Things NOT in Phase 3

These belong to later phases:

- **Markdown rendering** in notes/content fields → Phase 4
- **Portrait/map image uploads** → Phase 4
- **Tags and filtering** → Phase 4
- **Player wiki view** (respecting `is_player_visible` and `is_gm_only`) → Phase 6
- **Global search** across all entity types → after Phase 3 is a good time to add this

---

## How to Use This File

Start a Claude Code session and open with:

> "Please read CLAUDE.md and phase-3-plan.md, then let's build Phase 3. Start with Step 1: Quest model and CRUD."

Work through each step, testing as you go. When a step is done, commit and move to the next.

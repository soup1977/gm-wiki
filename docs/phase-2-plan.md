# Phase 2 Plan — NPCs & Locations with Bidirectional Linking

## Goal
Build full CRUD (Create, Read, Update, Delete) for NPCs and Locations. Both entity types link to each other: an NPC has a home location, and a location page shows which NPCs live there. Everything is scoped to the active campaign.

When this phase is done, the core loop of the entire app works. Every future entity type follows this same pattern.

---

## Pre-Work: Add Flask-Migrate

Phase 1 uses `db.create_all()` to build tables. That works once, but it can't update existing tables when we add new columns or new models. Flask-Migrate solves this — it tracks database changes like Git tracks code changes.

### Steps
1. Install Flask-Migrate: `pip install Flask-Migrate`
2. Add to `requirements.txt`
3. Update `app/__init__.py`:
   - Import: `from flask_migrate import Migrate`
   - After creating `db`, add: `migrate = Migrate(app, db)`
   - **Remove** the `db.create_all()` block — migrations handle table creation now
4. Initialize migrations:
   - `flask db init` (creates a `migrations/` folder — only done once)
   - `flask db migrate -m "Initial migration from existing tables"` (detects current models)
   - `flask db stamp head` (tells migrate the database already matches the current models, so it won't try to recreate existing tables)
5. From now on, after any model change: `flask db migrate -m "description"` then `flask db upgrade`

---

## Database Models

All models go in `app/models.py`. The existing Campaign model stays as-is.

### NPC Model

```python
class NPC(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(200))           # e.g. "blacksmith", "villain"
    status = db.Column(db.String(50), default='alive')  # alive / dead / unknown / missing
    faction = db.Column(db.String(200))        # plain text for now
    physical_description = db.Column(db.Text)
    personality = db.Column(db.Text)
    secrets = db.Column(db.Text)               # GM-only, never shown to players
    notes = db.Column(db.Text)                 # general notes (markdown in Phase 4)
    is_player_visible = db.Column(db.Boolean, default=False)  # used in Phase 6

    # Foreign key to Location (NPC's home)
    home_location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=True)

    # Relationships
    campaign = db.relationship('Campaign', backref='npcs')
    home_location = db.relationship('Location', backref='npcs_living_here', foreign_keys=[home_location_id])
```

**Status choices** (use in forms, not enforced at DB level):
`['alive', 'dead', 'unknown', 'missing']`

### Location Model

```python
class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(100))           # city / dungeon / wilderness / etc (free text)
    description = db.Column(db.Text)
    gm_notes = db.Column(db.Text)              # GM-only, never shown to players
    notes = db.Column(db.Text)                 # general notes (markdown in Phase 4)
    is_player_visible = db.Column(db.Boolean, default=False)  # used in Phase 6

    # Self-referencing parent (region > city > district)
    parent_location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=True)

    # Relationships
    campaign = db.relationship('Campaign', backref='locations')
    parent_location = db.relationship('Location', remote_side='Location.id', backref='child_locations', foreign_keys=[parent_location_id])
```

### NPC ↔ Location "Connected Locations" Link Table

The home_location relationship above handles "this NPC lives here." But the scope doc also says Locations have "Notable NPCs" and NPCs might appear at multiple locations. We handle this with a many-to-many association table:

```python
npc_location_link = db.Table('npc_location_link',
    db.Column('npc_id', db.Integer, db.ForeignKey('npc.id'), primary_key=True),
    db.Column('location_id', db.Integer, db.ForeignKey('location.id'), primary_key=True)
)
```

Then add to the NPC model:
```python
    connected_locations = db.relationship('Location', secondary=npc_location_link,
                                          backref='notable_npcs')
```

### Location ↔ Location "Connected Locations" Link Table

Locations can connect to other locations (e.g. a road between two towns):

```python
location_connection = db.Table('location_connection',
    db.Column('location_a_id', db.Integer, db.ForeignKey('location.id'), primary_key=True),
    db.Column('location_b_id', db.Integer, db.ForeignKey('location.id'), primary_key=True)
)
```

Then add to the Location model:
```python
    connected_locations = db.relationship(
        'Location',
        secondary=location_connection,
        primaryjoin='Location.id == location_connection.c.location_a_id',
        secondaryjoin='Location.id == location_connection.c.location_b_id',
        backref='connected_from'
    )
```

> **Note for Claude Code:** This is a self-referential many-to-many, which is a bit tricky. The `primaryjoin` and `secondaryjoin` tell SQLAlchemy which side is which. When displaying connected locations on a Location page, you'll need to combine both `connected_locations` and `connected_from` to get the full list (since the link is stored one direction in the table).

### Migration

After adding all models:
```bash
flask db migrate -m "Add NPC and Location models with linking tables"
flask db upgrade
```

---

## Routes

All routes live in `app/routes/`. Create two new files: `npcs.py` and `locations.py`. Register them as blueprints in `app/__init__.py`.

### NPC Routes (`app/routes/npcs.py`)

| Route | Method | What It Does |
|-------|--------|--------------|
| `/npcs` | GET | List all NPCs in active campaign. Show name, role, status, home location. |
| `/npcs/new` | GET | Show the create NPC form. |
| `/npcs/new` | POST | Validate and save new NPC. Redirect to its detail page. |
| `/npcs/<id>` | GET | Show NPC detail page with all fields and linked entities. |
| `/npcs/<id>/edit` | GET | Show edit form pre-filled with current data. |
| `/npcs/<id>/edit` | POST | Validate and save changes. Redirect to detail page. |
| `/npcs/<id>/delete` | POST | Delete NPC. Redirect to NPC list. Use a confirmation prompt. |

**Important:** Every route must filter by `campaign_id` matching the active campaign. An NPC from Campaign A must never appear when Campaign B is active.

### Location Routes (`app/routes/locations.py`)

| Route | Method | What It Does |
|-------|--------|--------------|
| `/locations` | GET | List all Locations in active campaign. Show name, type, parent location. |
| `/locations/new` | GET | Show the create Location form. |
| `/locations/new` | POST | Validate and save new Location. Redirect to its detail page. |
| `/locations/<id>` | GET | Show Location detail page with all fields, child locations, and linked NPCs. |
| `/locations/<id>/edit` | GET | Show edit form pre-filled with current data. |
| `/locations/<id>/edit` | POST | Validate and save changes. Redirect to detail page. |
| `/locations/<id>/delete` | POST | Delete Location. Redirect to Location list. Use a confirmation prompt. |

**Important:** Same campaign scoping as NPCs.

---

## Templates

All templates go in `app/templates/`. Use the existing base template layout from Phase 1.

### NPC Templates

- **`npcs/list.html`** — Table or card list of all NPCs. Columns: Name (clickable link), Role, Status, Home Location (clickable link). Include a "New NPC" button at the top.
- **`npcs/detail.html`** — Full NPC page. Show all fields. Home Location and Connected Locations are clickable links. Show a sidebar or section for "Appears at Locations" (from the many-to-many link). Edit and Delete buttons visible.
- **`npcs/form.html`** — Shared form for both create and edit. Fields:
  - Name (text input, required)
  - Role (text input)
  - Status (dropdown: alive / dead / unknown / missing)
  - Faction (text input)
  - Home Location (dropdown of locations in this campaign, with blank "None" option)
  - Connected Locations (multi-select of locations in this campaign)
  - Physical Description (textarea)
  - Personality (textarea)
  - Secrets (textarea — label it "GM Only" clearly)
  - Notes (textarea)

### Location Templates

- **`locations/list.html`** — Table or card list of all Locations. Columns: Name (clickable link), Type, Parent Location (clickable link). Include a "New Location" button.
- **`locations/detail.html`** — Full Location page. Show all fields. Parent Location is a clickable link. Show child locations list (clickable). Show "Notable NPCs" section (from many-to-many) and "NPCs Living Here" section (from home_location backref). Connected Locations shown as clickable links. Edit and Delete buttons.
- **`locations/form.html`** — Shared form for create and edit. Fields:
  - Name (text input, required)
  - Type (text input)
  - Parent Location (dropdown of locations in this campaign, with blank "None" option — exclude self when editing)
  - Connected Locations (multi-select of locations in this campaign — exclude self)
  - Description (textarea)
  - GM-Only Notes (textarea — label it clearly)
  - Notes (textarea)

### Navigation Update

Update the main nav bar to include links to "NPCs" and "Locations" lists. These should only appear when a campaign is active.

---

## Build Order

Follow this order so each piece can be tested before moving on:

### Step 1: Flask-Migrate setup
- Install, configure, create initial migration
- Verify the existing Campaign table still works
- **Branch:** `feature/flask-migrate`
- **Commit:** "Add Flask-Migrate and create initial migration"

### Step 2: Location model + CRUD (do this BEFORE NPCs)
- Add Location model to `models.py`
- Run migration
- Create Location blueprint with all routes
- Create all three Location templates
- Test: create, view, edit, delete a location
- Test: parent/child location nesting works
- **Branch:** `feature/location-crud`
- **Commits:**
  - "Add Location model and migration"
  - "Add Location routes and templates"
  - "Add parent-child location nesting"

### Step 3: NPC model + CRUD
- Add NPC model to `models.py` (including the `home_location_id` foreign key)
- Run migration
- Create NPC blueprint with all routes
- Create all three NPC templates
- Test: create, view, edit, delete an NPC
- Test: Home Location dropdown shows locations from current campaign
- **Branch:** `feature/npc-crud`
- **Commits:**
  - "Add NPC model and migration"
  - "Add NPC routes and templates"

### Step 4: Bidirectional linking
- Add the `npc_location_link` association table
- Add the `location_connection` association table
- Add the `connected_locations` relationships to both models
- Run migration
- Update NPC form to include Connected Locations multi-select
- Update Location form to include Connected Locations multi-select
- Update NPC detail page to show connected locations
- Update Location detail page to show notable NPCs, NPCs living here, and connected locations
- Test: Link an NPC to multiple locations, verify it shows on both sides
- Test: Connect two locations, verify it shows on both sides
- **Branch:** `feature/entity-linking`
- **Commits:**
  - "Add NPC-Location and Location-Location link tables"
  - "Add bidirectional linking to NPC and Location forms"
  - "Show linked entities on detail pages"

### Step 5: Navigation + polish
- Add NPCs and Locations links to the nav bar (only when campaign is active)
- Add breadcrumb-style navigation on detail pages (e.g. Locations > Waterdeep > Edit)
- Test the full loop: create campaign → create locations → create NPCs → link them → verify cross-references work both directions
- **Branch:** `feature/phase2-nav-polish`
- **Commit:** "Update navigation and add breadcrumbs for Phase 2 entities"

---

## Things NOT in Phase 2

These are listed in the scope doc but belong to later phases:

- **Portrait images / Map images** → Phase 4
- **Tags** → Phase 4
- **Markdown rendering** in notes → Phase 4 (fields exist now as plain text)
- **File attachments** → Phase 4
- **Player visibility toggle logic** → Phase 6 (the `is_player_visible` column exists, but nothing uses it yet)
- **Global search** → can add after Phase 3 when all entity types exist

---

## How to Use This File

Drop this file in your repo root. Start a Claude Code session and open with:

> "Please read CLAUDE.md and phase-2-plan.md, then let's build Phase 2. Start with the Flask-Migrate setup (Step 1)."

Work through each step, testing as you go. When a step is done, commit and move to the next.

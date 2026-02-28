# GM Wiki — Phase 5.5: Bestiary & Monster Instances

## Overview
Add a global Bestiary system for managing monster/creature templates and campaign-scoped Monster Instances for tracking specific creatures encountered during play. Includes "Promote to NPC" functionality for creatures that become story-important.

---

## Goals
1. Create global Bestiary Entries (shared across all campaigns)
2. Build Monster Instance system (campaign-scoped creature records)
3. Link instances to Sessions for encounter tracking
4. Enable "Promote to NPC" workflow for important creatures
5. Player Wiki view shows Bestiary name + image + tags only

---

## Database Models

### 1. BestiaryEntry (Global, No Campaign Scope)

**Table:** `bestiary_entries`

```python
class BestiaryEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    system = db.Column(db.String(50))  # "D&D 5e", "ICRPG", etc. (optional)
    cr_level = db.Column(db.String(20))  # "CR 1/4", "Level 3", etc. (optional)
    stat_block = db.Column(db.Text, nullable=False)  # Markdown-supported
    image_path = db.Column(db.String(255))  # Portrait/token image
    source = db.Column(db.String(100))  # "Monster Manual p.166", "Homebrew"
    visible_to_players = db.Column(db.Boolean, default=False)
    tags = db.Column(db.Text)  # JSON array: ["humanoid", "goblinoid", "common"]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    instances = db.relationship('MonsterInstance', backref='bestiary_entry', lazy=True, cascade='all, delete-orphan')
```

**Key Points:**
- NO campaign_id — this is global
- Tags stored as JSON for flexible filtering
- Markdown support in stat_block field
- Cascade delete: deleting a Bestiary Entry deletes all its instances

### 2. MonsterInstance (Campaign-Scoped)

**Table:** `monster_instances`

```python
class MonsterInstance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bestiary_entry_id = db.Column(db.Integer, db.ForeignKey('bestiary_entry.id'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    
    instance_name = db.Column(db.String(100), nullable=False)  # "Goblin 1", "Snarl"
    status = db.Column(db.String(20), default='alive')  # alive / dead / fled / unknown
    notes = db.Column(db.Text)  # GM-only notes about this specific creature
    
    promoted_to_npc_id = db.Column(db.Integer, db.ForeignKey('npc.id'))  # NULL until promoted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    campaign = db.relationship('Campaign', backref='monster_instances')
    promoted_npc = db.relationship('NPC', backref='original_monster_instance', foreign_keys=[promoted_to_npc_id])
    sessions = db.relationship('Session', secondary='session_monsters', backref='monsters_encountered')
```

**Key Points:**
- Scoped to campaign (instances don't cross campaigns)
- Links back to global Bestiary Entry
- Tracks status across sessions
- Optional promotion to full NPC

### 3. Session-Monster Link Table (Many-to-Many)

**Table:** `session_monsters`

```python
session_monsters = db.Table('session_monsters',
    db.Column('session_id', db.Integer, db.ForeignKey('session.id'), primary_key=True),
    db.Column('monster_instance_id', db.Integer, db.ForeignKey('monster_instance.id'), primary_key=True)
)
```

**Key Points:**
- Many sessions can reference the same monster instance (recurring enemies)
- Many monster instances can appear in the same session

---

## User Flows

### Flow 1: Create Bestiary Entry

**Route:** `/bestiary/create`

1. GM clicks "Add Bestiary Entry" from Bestiary index
2. Form fields:
   - Name (required)
   - System (optional text field)
   - CR/Level (optional text field)
   - Stat Block (large textarea, required, Markdown-enabled)
   - Image upload (optional)
   - Source (text field)
   - Tags (multi-select or comma-separated input)
   - Visible to Players (checkbox, default unchecked)
3. Submit creates global Bestiary Entry
4. Redirect to Bestiary Entry detail page

**Notes:**
- No campaign dropdown — this is global
- Consider tag autocomplete from existing tags

### Flow 2: View Bestiary Entry

**Route:** `/bestiary/<id>`

**GM View Shows:**
- Name, System, CR/Level
- Stat Block (rendered Markdown)
- Image
- Source, Tags
- List of Monster Instances spawned from this entry (grouped by campaign)
- "Spawn Instance" button
- Edit/Delete buttons

**Player View Shows (if visible_to_players=True):**
- Name
- Image
- Tags
- Source
- NO stat block, CR/Level, system

### Flow 3: Spawn Monster Instance

**Route:** `/bestiary/<id>/spawn` (POST)

**Context:** Can be triggered from:
- Bestiary Entry detail page ("Spawn Instance" button)
- Combat Tracker (future Phase 5 feature)
- Session planning (future feature)

**Process:**
1. Select active campaign (pre-filled from session)
2. Optional: Enter instance name (default auto-generates: "Goblin 1", "Goblin 2", etc.)
3. Submit creates MonsterInstance record
4. Redirect to Monster Instance detail page

**Auto-Numbering Logic:**
- Query existing instances of this bestiary entry in current campaign
- Find highest number in instance_name pattern
- Increment by 1
- Example: "Goblin 1", "Goblin 2" exist → new one becomes "Goblin 3"

### Flow 4: View Monster Instance

**Route:** `/campaigns/<campaign_id>/monsters/<instance_id>`

**Shows:**
- Instance name (editable)
- Status (dropdown: alive/dead/fled/unknown)
- Bestiary Entry link (click to see full stat block)
- Sessions appeared in (list with links)
- GM-only notes (textarea)
- "Promote to NPC" button (if not already promoted)
- Edit/Delete buttons

**If promoted:**
- Show "Promoted to NPC: [NPC Name]" with link
- Disable "Promote to NPC" button

### Flow 5: Promote to NPC

**Route:** `/campaigns/<campaign_id>/monsters/<instance_id>/promote` (GET + POST)

**GET (form page):**
- Pre-filled NPC creation form:
  - Name: Instance name (editable, e.g. change "Goblin 1" to "Snarl")
  - Status: Pulled from instance status
  - Portrait: Copied from Bestiary Entry image
  - Sessions Appeared: Auto-populated from instance history
- Empty fields for GM to fill:
  - Role, Faction, Home Location
  - Physical Description, Personality
  - Secrets (GM-only)
  - Markdown Notes

**POST (submit):**
1. Create new NPC record with form data
2. Update MonsterInstance.promoted_to_npc_id = new NPC id
3. Copy session links from instance to NPC
4. Redirect to new NPC detail page

**Notes:**
- Original MonsterInstance record persists (historical record)
- NPC page should show "Origin: Monster Instance #47" with link

### Flow 6: Link Instances to Sessions

**Two approaches:**

**A. From Session Edit Page:**
- Add "Monsters Encountered" section
- Multi-select dropdown of campaign's Monster Instances
- Save links via session_monsters table

**B. From Monster Instance Page:**
- "Add to Session" button
- Select session from dropdown
- Save link

**Recommend both** — flexible linking from either direction

---

## Routes & Views

### Bestiary Routes (Global)

| Route | Method | Purpose |
|-------|--------|---------|
| `/bestiary` | GET | List all Bestiary Entries (filter by tag, search) |
| `/bestiary/create` | GET, POST | Create new Bestiary Entry |
| `/bestiary/<id>` | GET | View Bestiary Entry detail |
| `/bestiary/<id>/edit` | GET, POST | Edit Bestiary Entry |
| `/bestiary/<id>/delete` | POST | Delete Bestiary Entry (+ confirm modal) |
| `/bestiary/<id>/spawn` | POST | Spawn new Monster Instance |

### Monster Instance Routes (Campaign-Scoped)

| Route | Method | Purpose |
|-------|--------|---------|
| `/campaigns/<campaign_id>/monsters` | GET | List Monster Instances for campaign |
| `/campaigns/<campaign_id>/monsters/<instance_id>` | GET | View Monster Instance detail |
| `/campaigns/<campaign_id>/monsters/<instance_id>/edit` | GET, POST | Edit Monster Instance |
| `/campaigns/<campaign_id>/monsters/<instance_id>/delete` | POST | Delete Monster Instance |
| `/campaigns/<campaign_id>/monsters/<instance_id>/promote` | GET, POST | Promote to NPC |

### Navigation Integration

**Main Nav:**
- Add "Bestiary" link (global, always visible)

**Campaign-Scoped Nav:**
- Add "Monster Instances" under campaign dropdown or entities section

---

## Templates

### bestiary/index.html
- List of all Bestiary Entries
- Filter by tag (clickable tag cloud or dropdown)
- Search bar
- "Create New Entry" button
- Table/card view showing: name, image thumbnail, tags, CR/level, instance count

### bestiary/detail.html
- Full stat block (Markdown rendered)
- Image display
- Tags, source, system, CR/level
- "Spawn Instance" button
- "Edit Entry" / "Delete Entry" buttons
- Instances section: grouped by campaign, list of spawned instances

### bestiary/form.html
- Reusable form for create/edit
- Fields: name, system, CR/level, stat_block (textarea), image upload, source, tags, visible_to_players

### monsters/index.html (campaign-scoped)
- List of Monster Instances for active campaign
- Filter by status, Bestiary Entry type
- Table showing: instance name, bestiary entry, status, sessions appeared
- "Spawn New Instance" button (opens modal or goes to bestiary)

### monsters/detail.html
- Instance name, status, notes
- Link to Bestiary Entry (view full stat block)
- Sessions appeared in (list with links)
- "Promote to NPC" button
- Edit/Delete buttons

### monsters/promote_form.html
- Pre-filled NPC creation form
- Clear indication this is promoting a monster instance
- Submit creates NPC and links it

---

## Player Wiki Integration

### Bestiary in Player Wiki

**Route:** `/wiki/bestiary` (or similar player-facing URL)

**Shows only entries where `visible_to_players = True`:**
- Name
- Image
- Tags
- Source

**Hides:**
- Stat Block
- CR/Level
- System
- All instances (players don't see "Goblin #47 appeared in Session 12")

**Layout:**
- Card/gallery view with images
- Filter by tag
- Search by name
- Click card → simple detail page (name, image, tags, source only)

---

## Tag System

### Tag Storage
- Store as JSON array in `tags` column
- Example: `["humanoid", "goblinoid", "common", "forest"]`

### Common Tag Categories
**Creature Type:** humanoid, dragon, undead, aberration, beast, construct, elemental, fey, fiend, giant, monstrosity, ooze, plant  
**Power Level:** minion, standard, elite, boss, legendary  
**Environment:** forest, dungeon, urban, aquatic, mountain, planar, desert  
**System:** dnd5e, icrpg, pathfinder, homebrew  
**Custom:** Any GM-defined tags

### UI Features
- Tag input: Comma-separated or multi-select with autocomplete
- Tag cloud on index page (clickable filters)
- Multi-tag filtering (AND logic: "dragon" + "boss" = only boss dragons)

---

## Database Migration

Since you're using `db.create_all()` currently:

1. Add model definitions to `models.py`
2. Run `db.create_all()` to create new tables
3. No data migration needed (new feature)

**Future consideration:** When you eventually adopt Flask-Migrate, these tables will be included in the schema.

---

## Testing Checklist

### Bestiary Entry CRUD
- [ ] Create global Bestiary Entry
- [ ] View Bestiary Entry with Markdown stat block rendered
- [ ] Edit Bestiary Entry
- [ ] Delete Bestiary Entry (confirm instances are deleted too)
- [ ] Upload image to Bestiary Entry
- [ ] Add tags to entry
- [ ] Filter Bestiary by tag
- [ ] Search Bestiary by name

### Monster Instances
- [ ] Spawn instance from Bestiary Entry
- [ ] Auto-numbering works ("Goblin 1", "Goblin 2", etc.)
- [ ] View Monster Instance detail
- [ ] Edit instance name, status, notes
- [ ] Link instance to Session
- [ ] View sessions on instance detail page
- [ ] View instances on session detail page
- [ ] Delete instance (doesn't affect Bestiary Entry)

### Promote to NPC
- [ ] Click "Promote to NPC" on instance
- [ ] Form pre-fills with instance data
- [ ] Submit creates NPC with correct data
- [ ] NPC links back to original instance
- [ ] Instance shows "Promoted to NPC: [name]"
- [ ] Session links carry over to NPC
- [ ] "Promote" button disabled after promotion

### Player Wiki
- [ ] Bestiary visible in Player Wiki (if toggle enabled)
- [ ] Only name, image, tags, source shown to players
- [ ] Stat block, CR/level, system hidden from players
- [ ] Monster Instances NOT visible to players (only Bestiary Entries)

---

## Implementation Order

### Step 1: Bestiary Entry Model & CRUD
- Add BestiaryEntry model
- Create routes and views for CRUD
- Build form template
- Test basic create/edit/delete

### Step 2: Monster Instance Model & Basic CRUD
- Add MonsterInstance model
- Add session_monsters link table
- Create routes and views for instances
- Build spawning logic (auto-numbering)
- Link instances to sessions

### Step 3: Promote to NPC
- Add promote route and form
- Pre-fill logic from instance data
- Link creation and instance update
- Test full workflow

### Step 4: Player Wiki Integration
- Add Bestiary to player wiki nav
- Filter logic for visible_to_players
- Template for player-facing Bestiary view
- Hide stat blocks and instances

### Step 5: Tag System & Filtering
- Tag input/storage
- Tag cloud display
- Filter logic
- Autocomplete for existing tags

### Step 6: Polish & Navigation
- Add Bestiary to main nav
- Add Monster Instances to campaign nav
- Breadcrumbs on all pages
- Image display improvements

---

## Future Enhancements (Post-Phase 5.5)

### Import/Scrape from URLs
- Add "Import from URL" button on Bestiary create page
- Scrape D&D Beyond, AI20, or similar
- Parse HTML to extract name, stats, description
- GM reviews and saves

**Why not now:**
- Scraping is fragile (sites change)
- Different systems = different scrape logic
- Copyright gray area
- Can manually paste stat blocks for MVP

### Combat Tracker Integration
- Spawn instances directly from Combat Tracker
- Track HP, conditions, initiative (ephemeral combat data)
- HP resets to full each time instance is added to combat
- Save instance to session after combat ends

### Bulk Instance Creation
- "Add 10 goblins" button
- Auto-generates instances with sequential numbering
- Saves time for large encounters

### Advanced Filtering
- Filter instances by session appeared
- Filter by status (show all fled creatures)
- "Recurring enemies" view (instances in 3+ sessions)

---

## Notes for Claude Code

- **No Campaign Scope on Bestiary Entries** — These are global, no `campaign_id` field
- **Monster Instances ARE Campaign-Scoped** — Always filter by active campaign
- **Auto-Numbering Logic** — Find existing instances, parse numbers, increment
- **Cascade Deletes** — Deleting Bestiary Entry should delete all its instances (warn GM!)
- **Markdown Rendering** — Use same logic as existing entities (NPCs, Locations, etc.)
- **Image Uploads** — Use same pattern as NPC portraits, Location maps
- **Session Links** — Use many-to-many table, same pattern as NPCs↔Sessions

---

## Git Workflow

**Branch:** `feature/bestiary-system`

**Commits (suggested sequence):**
1. "Add BestiaryEntry model and database schema"
2. "Add Bestiary CRUD routes and views"
3. "Add MonsterInstance model and session linking"
4. "Add monster instance spawning and auto-numbering"
5. "Add promote-to-NPC functionality"
6. "Add Bestiary to player wiki view"
7. "Add tag filtering and search to Bestiary"
8. "Update navigation with Bestiary and Monster Instance links"

**Pull Request:** Merge to `main` when all testing checklist items pass

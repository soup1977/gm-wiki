GM Wiki — Phase 5 Plan: Live Table Tools & Player Characters
Status: Ready for implementation
Prerequisites: Phase 1, 2, 3, and 4 must be complete
Git Strategy: One feature branch per major component, PR to main

Overview
Phase 5 adds the tools needed for live gameplay at the table: Player Character tracking, Combat Tracker, Random Tables, and Session Mode Dashboard. This phase transforms GM Wiki from a reference tool into an active play aid.
What We're Building

Player Characters — Lightweight PC tracking with flexible stat system
Combat Tracker — Ephemeral encounter management with initiative and HP tracking
Random Tables — Custom per-campaign tables + built-in generic tables
Session Mode Dashboard — Focused live-play view that ties everything together

Key Principles

System-agnostic: Works for D&D, ICRPG, Pathfinder, homebrew systems
Tablet-friendly: Big touch targets, readable at arm's length
Quick reference: GM needs info fast during active play
Ephemeral combat: Combat Tracker doesn't clutter the database with temporary data


Part 1: Player Characters
Why Player Characters Are Separate from NPCs

Different fields: PCs need player name, level, flexible stats; NPCs need faction, secrets, role
Different visibility: NPCs toggle player visibility; PCs are GM reference only (players have their own sheets)
Different usage: PCs appear in Session Mode and Combat Tracker; NPCs are world entities
Cleaner navigation: "NPCs" vs "Player Characters" makes UI obvious

Data Model
PlayerCharacter Model
pythonclass PlayerCharacter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    
    # Basic Info
    character_name = db.Column(db.String(200), nullable=False)
    player_name = db.Column(db.String(200), nullable=False)
    level_or_rank = db.Column(db.String(100))  # "Level 5", "CR 3", "Veteran"
    class_or_role = db.Column(db.String(200))  # "Fighter", "Hacker", "Pilot"
    
    # Status
    status = db.Column(db.String(50), default='active')  
    # Values: active, inactive, retired, dead, npc
    
    # Content
    notes = db.Column(db.Text)  # Markdown-supported GM notes
    portrait_filename = db.Column(db.String(255))  # Image upload (Phase 4 pattern)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    campaign = db.relationship('Campaign', backref='player_characters')
    stats = db.relationship('PlayerCharacterStat', backref='character', cascade='all, delete-orphan')
    session_attendances = db.relationship('SessionAttendance', backref='character', cascade='all, delete-orphan')
CampaignStatTemplate Model
Defines what stats are tracked for PCs in this campaign.
pythonclass CampaignStatTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    
    # Stat definition
    stat_name = db.Column(db.String(100), nullable=False)  # "Armor Class", "Max HP", etc.
    display_order = db.Column(db.Integer, default=0)  # For sorting display
    
    # Relationship
    campaign = db.relationship('Campaign', backref='stat_template_fields')
Notes:

Each campaign has multiple CampaignStatTemplate rows (one per stat field)
Example: Campaign "Curse of Strahd" has template fields: "AC", "Max HP", "Spell Save DC", "Passive Perception"

PlayerCharacterStat Model
Stores actual stat values for each PC.
pythonclass PlayerCharacterStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('player_character.id'), nullable=False)
    template_field_id = db.Column(db.Integer, db.ForeignKey('campaign_stat_template.id'), nullable=False)
    
    # Value
    stat_value = db.Column(db.String(100))  # Stores as string: "16", "45", "1d8+3"
    
    # Relationships
    template_field = db.relationship('CampaignStatTemplate')
Notes:

Each PC has one PlayerCharacterStat row per template field
When template changes (add/remove stat), we need migration logic

SessionAttendance Model (Many-to-Many)
Tracks which PCs attended which sessions.
pythonclass SessionAttendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey('player_character.id'), nullable=False)
    
    # Relationships
    session = db.relationship('Session', backref='attendances')
    # character backref defined in PlayerCharacter model above
Stat Template Preset System
When creating a campaign, GM selects a game system preset to auto-populate stat template fields.
Hardcoded Presets (Python dict)
pythonSTAT_PRESETS = {
    'dnd5e': {
        'name': 'D&D 5e',
        'stats': [
            'Armor Class (AC)',
            'Max Hit Points',
            'Spell Save DC',
            'Passive Perception',
            'Passive Investigation',
            'Passive Insight'
        ]
    },
    'pathfinder2e': {
        'name': 'Pathfinder 2e',
        'stats': [
            'Armor Class (AC)',
            'Max Hit Points',
            'Perception',
            'Fortitude Save',
            'Reflex Save',
            'Will Save',
            'Class DC'
        ]
    },
    'icrpg': {
        'name': 'ICRPG',
        'stats': [
            'Armor',
            'Hearts (Max HP)',
            'Basic Effort',
            'Weapons/Tools Effort',
            'Magic Effort',
            'Ultimate Effort'
        ]
    },
    'custom': {
        'name': 'Custom',
        'stats': [
            'Stat 1',
            'Stat 2',
            'Stat 3',
            'Stat 4'
        ]
    }
}
```

#### Campaign Creation Flow (Updated)

**Step 1:** Existing campaign form fields (name, system, status, description)

**Step 2 (NEW):** PC Stat Template Selection
- Dropdown: "Select game system for player stats"
- Options: "D&D 5e", "Pathfinder 2e", "ICRPG", "Custom"
- On selection, show preview of stat fields that will be created
- Note: "You can edit these fields later in Campaign Settings"

**Step 3:** On campaign creation:
- Create Campaign record
- Create `CampaignStatTemplate` rows based on selected preset
- Redirect to campaign detail page

#### Campaign Settings — Edit Stat Template

New section on campaign settings page:

**"Player Character Stat Fields"**
- Display current template fields in order
- Each field shows:
  - Stat name (editable inline)
  - Delete button
  - Drag handle for reordering (nice-to-have, can use up/down arrows)
- "Add New Stat Field" button
- Save button

**Migration Logic When Template Changes:**
- **Add new field:** Create `PlayerCharacterStat` rows for all existing PCs (value = empty)
- **Delete field:** Cascade delete all `PlayerCharacterStat` rows for that field
- **Rename field:** Just update the template field name (stat values stay intact)

### Player Character CRUD

#### Routes
```
/pcs — List all PCs in active campaign
/pcs/create — Create new PC form
/pcs/<id> — PC detail page
/pcs/<id>/edit — Edit PC form
/pcs/<id>/delete — Delete PC (POST with confirmation)
```

#### PC List Page (`/pcs`)

**Layout:**
- Page title: "Player Characters — [Campaign Name]"
- "Create New PC" button (top right)
- Filter/tabs by status: All / Active / Inactive / Retired / Dead / NPC
- Table or card grid showing:
  - Portrait thumbnail
  - Character name
  - Player name
  - Class/Role
  - Level/Rank
  - Status badge
  - Quick stats preview (first 3 stat fields)
  - Edit/Delete buttons

**Empty State:**
- "No player characters yet. Create your first PC to get started!"

#### PC Detail Page (`/pcs/<id>`)

**Layout:**
- Portrait (large)
- Character Name (heading)
- Player Name (subheading)
- Class/Role, Level/Rank, Status badge
- **Stats Section:**
  - Display all stats in grid/table format
  - Stat name + value
  - "Edit Stats" button → inline editing or modal
- **Notes Section:**
  - Markdown-rendered GM notes
  - "Edit Notes" button
- **Sessions Attended:**
  - List of sessions this PC attended (links to session detail)
  - Count: "Attended 12 of 15 sessions"
- Edit/Delete buttons

#### PC Create/Edit Form

**Fields:**
- Character Name (required)
- Player Name (required)
- Class/Role (optional)
- Level/Rank (optional)
- Status (dropdown: active/inactive/retired/dead/npc)
- Portrait upload (Phase 4 pattern)
- **Stat Values:**
  - Show all template fields from campaign
  - Each stat gets an input field
  - Use template field name as label
  - Example: "Armor Class (AC): [___]"
- Notes (Markdown textarea)
- Save/Cancel buttons

**Validation:**
- Character name required
- Player name required
- Stat values are optional (can be filled in later)

### Session Attendance Management

#### Update Session Edit Page

Add new section: **"Player Attendance"**

**Layout:**
- Checklist of all active PCs in campaign
- Checkbox per PC: [✓] Character Name (Player Name)
- Show portrait thumbnails next to names
- Status filter: Show only Active PCs by default, toggle to show all

**Save Logic:**
- On session save, update `SessionAttendance` table
- Delete existing attendance records for this session
- Create new records for checked PCs

#### Session Detail Page Update

Add section showing which PCs attended:
- "Players: Alice (Thorin), Bob (Gimli), Carol (Legolas)"
- Or card layout with portraits

---

## Part 2: Combat Tracker

### Design Principles

- **Ephemeral:** Combat data doesn't persist to database (optional save to session in future)
- **Session-scoped:** Uses browser session storage or temporary server-side state
- **Auto-populate PCs:** Pull PCs from current session context (set by Session Mode)
- **Mobile-friendly:** Big buttons, clear initiative order, readable stats

### Data Storage Strategy

**Option A:** Browser Session Storage (Recommended for Phase 5)
- Store combat state in `sessionStorage` (resets on browser close)
- No database writes
- Simple, fast, no cleanup needed
- Loss of data if browser crashes (acceptable for ephemeral tool)

**Option B:** Temporary Database Table
- `CombatEncounter` table with `is_active` flag
- Auto-delete old encounters on app restart
- More complex but could save to Session record later

**Decision:** Use **Option A** for Phase 5. Session Storage is simpler and fits the "ephemeral" design.

### Combat Tracker UI

#### Route
```
/combat-tracker — Main combat interface
Access

Link in Session Mode Dashboard ("Launch Combat Tracker")
Link in main nav (always accessible)
When launched from Session Mode, auto-populate PCs from current session

Layout
Top Section: Combat Controls

Round counter: "Round 3"
"Next Turn" button (big, primary action)
"End Combat" button (clear tracker, confirmation modal)

Main Section: Initiative Order

Vertical list of combatants sorted by initiative
Each combatant card shows:

Name
Initiative score
Current HP / Max HP (editable inline)
HP bar (visual indicator)
Status effect checkboxes (see below)
"Remove from Combat" button
Current turn indicator: Highlight active combatant


Drag to reorder (nice-to-have) or manual initiative editing

Status Effects Checklist (per combatant):

Poisoned
Stunned
Prone
Restrained
Blinded
Deafened
Frightened
Grappled
Incapacitated
Invisible
Paralyzed
Petrified
Charmed
Unconscious
Other (free text)

Add Combatant Section:

"Add Combatant" button opens modal/form:

Name (text input)
Initiative (number input)
Max HP (number input)
Current HP (auto-fills to max)
Quick Add PC: Dropdown of PCs from current session (if session context exists)

Selecting a PC pre-fills name and stats


Quick Add Monster: Name + HP only (GM references stat block elsewhere)


"Add" button

Monster Stat Block Panel (collapsible sidebar or modal):

Free-text area for pasting stat blocks
GM can copy/paste from PDFs or type quick reference
No parsing, just display
Example use: Paste goblin stats for quick reference during combat

Session Context Integration
If launched from Session Mode:

Get current session ID from session context
Query SessionAttendance for PCs in that session
Auto-populate option:

On Combat Tracker load, show banner: "Auto-add PCs from [Session Name]?"
Button: "Add All PCs" → creates combatant entries for all attending PCs
Pre-fills name and stats from PC records
GM sets initiative manually or uses random roll helper



If launched standalone (not from Session Mode):

No auto-populate
GM adds combatants manually

JavaScript Logic (Session Storage)
javascript// Combat state structure
{
  round: 1,
  currentTurnIndex: 0,
  combatants: [
    {
      id: "uuid",
      name: "Thorin",
      initiative: 18,
      currentHp: 45,
      maxHp: 52,
      statusEffects: ["poisoned"],
      isPC: true,
      characterId: 3  // Links to PlayerCharacter if PC
    },
    {
      id: "uuid",
      name: "Goblin 1",
      initiative: 12,
      currentHp: 7,
      maxHp: 7,
      statusEffects: [],
      isPC: false
    }
  ],
  monsterStatBlock: "Goblin: AC 15, HP 7, Scimitar +4 (1d6+2)"
}
Functions:

saveCombatState() — Write to sessionStorage
loadCombatState() — Read from sessionStorage
nextTurn() — Increment currentTurnIndex, roll to next round if needed
addCombatant(data) — Add to combatants array, re-sort by initiative
removeCombatant(id) — Remove from array
updateHp(id, newHp) — Update combatant HP
toggleStatusEffect(id, effect) — Add/remove status effect
endCombat() — Clear sessionStorage


Part 3: Random Tables
Two-Layer System

Built-in Generic Tables: Always available, read-only, all campaigns can use
Custom Per-Campaign Tables: GM creates per campaign, fully editable

Data Model
RandomTable Model
pythonclass RandomTable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=True)
    # If campaign_id is NULL, it's a built-in table
    
    # Table Info
    name = db.Column(db.String(200), nullable=False)  # "NPC Names", "Weather"
    category = db.Column(db.String(100))  # "Names", "Encounters", "Treasure"
    description = db.Column(db.Text)  # Optional description
    is_builtin = db.Column(db.Boolean, default=False)  # True for system tables
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    campaign = db.relationship('Campaign', backref='random_tables')
    rows = db.relationship('TableRow', backref='table', cascade='all, delete-orphan', order_by='TableRow.display_order')
TableRow Model
pythonclass TableRow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('random_table.id'), nullable=False)
    
    # Row Data
    content = db.Column(db.Text, nullable=False)  # The actual result text
    weight = db.Column(db.Integer, default=1)  # For weighted rolls (1 = normal)
    display_order = db.Column(db.Integer, default=0)  # For manual ordering
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### Custom Tables — CRUD

#### Routes
```
/random-tables — List all tables (built-in + campaign custom)
/random-tables/create — Create new custom table
/random-tables/<id> — Table detail (view rows, roll button)
/random-tables/<id>/edit — Edit table (name, category, description)
/random-tables/<id>/delete — Delete table (POST)
/random-tables/<id>/rows/add — Add row to table
/random-tables/<id>/rows/<row_id>/edit — Edit row
/random-tables/<id>/rows/<row_id>/delete — Delete row
/random-tables/<id>/roll — Roll on table (AJAX endpoint)
Table List Page (/random-tables)
Layout:

Page title: "Random Tables"
"Create New Table" button
Tabs: All / Built-in / Custom
Category filter dropdown
Table cards/list showing:

Table name
Category badge
Row count ("23 entries")
"Roll" button (quick roll, shows result modal)
Edit/Delete buttons (only for custom tables)



Table Detail Page (/random-tables/<id>)
Layout:

Table name (heading)
Category, description
Big "Roll on This Table" button → Triggers roll, shows result modal
Rows section:

List all rows
Show content, weight (if not 1)
Edit/Delete buttons per row (if custom table)
"Add New Row" button (if custom table)
Reorder buttons (up/down arrows) or drag-to-reorder



Create/Edit Table Form
Fields:

Table Name (required)
Category (free text, suggest common ones: "Names", "Encounters", "Treasure", "Events")
Description (optional)
Rows: Add/edit inline or on separate page (your choice)

Add/Edit Row Form (Modal or Separate Page)
Fields:

Content (text area, required) — the result text
Weight (number, default 1) — for weighted probability
Display order (auto-assigned, manually adjustable)

Roll Logic
Weighted Random Selection Algorithm
pythondef roll_on_table(table_id):
    table = RandomTable.query.get_or_404(table_id)
    rows = table.rows
    
    if not rows:
        return None
    
    # Build weighted list
    weighted_rows = []
    for row in rows:
        weighted_rows.extend([row] * row.weight)
    
    # Random selection
    import random
    selected_row = random.choice(weighted_rows)
    
    return {
        'table_name': table.name,
        'result': selected_row.content,
        'timestamp': datetime.utcnow()
    }
```

#### Roll Result Display

- AJAX call to `/random-tables/<id>/roll`
- Show result in modal:
  - Table name
  - Result text (large, readable)
  - "Roll Again" button
  - "Close" button
- Optional: Save roll history to session (not database)

### Built-in Tables — Seed Data

#### Implementation Strategy

**Option A:** Seed data in migration
- Create migration that inserts built-in tables
- Mark with `is_builtin=True`, `campaign_id=NULL`

**Option B:** Fixture file loaded on app init
- JSON or Python dict with table definitions
- Load on first run or via CLI command

**Decision:** Use **Option A** — migration ensures tables exist after db setup.

#### Initial Built-in Tables

**1. Fantasy NPC Names (Male)**
Category: Names
Rows: Thorin, Aldric, Gareth, Bram, Cedric, Dorian, Elric, Finnian, etc. (20-30 names)

**2. Fantasy NPC Names (Female)**
Category: Names
Rows: Lyra, Elara, Seraphina, Mira, Brynn, etc. (20-30 names)

**3. Weather**
Category: Environment
Rows: Clear skies, Light rain, Heavy rain, Fog, Snow, Sleet, Thunderstorm, Overcast, Windy, etc.

**4. Tavern Names**
Category: Locations
Rows: The Prancing Pony, The Dragon's Flagon, The Rusty Nail, The Silver Serpent, etc. (15-20 names)

**5. Dungeon Features**
Category: Encounters
Rows: Crumbling statue, Ancient murals, Strange glowing fungi, Collapsed ceiling, Hidden alcove, etc. (20+ features)

**6. Random Encounter (Generic)**
Category: Encounters
Rows: Wandering merchant, Hostile bandits, Curious animals, Fellow adventurers, Mysterious stranger, etc.

**Note:** Keep built-in tables generic and system-agnostic. GMs create campaign-specific tables for system mechanics.

---

## Part 4: Session Mode Dashboard

### Purpose

A **focused live-play view** for when the GM is actively running a game. Shows essential info at a glance and quick-launch buttons for live tools.

### Route
```
/session-mode — Main dashboard
/session-mode/set-session/<id> — Set current session (POST)
Session Context Management
How "Current Session" Works:

GM selects a session from dropdown: "Which session are you running?"
Session ID stored in Flask session (session['current_session_id'])
Persists across page loads until GM changes it or browser session ends
Used by Combat Tracker to auto-populate PCs

Selection UI:

Dropdown at top of Session Mode Dashboard
Shows recent sessions (last 10) + "Create New Session" link
On selection, page reloads with new session context

Dashboard Layout
Top Section: Session Info

Session title, number, date
"Edit Session" link
"Change Session" button (triggers session picker modal)

Main Content Grid (3-column layout on desktop, stacks on mobile)
Column 1: Active Quests

List of quests with status "Active"
Show quest name (linked), hook preview
Badge: "Active" in green
Empty state: "No active quests"

Column 2: Active Location

Dropdown: "Set Active Location"
Shows selected location's description (truncated)
Map image (if exists)
"View Full Location" link
Empty state: "No location set"

Column 3: Pinned NPCs

List of NPCs marked as "pinned for this session"
Show portrait thumbnail, name, role
"Manage Pinned NPCs" button → modal with checklist
Empty state: "No NPCs pinned"

Bottom Section: Session Summary

Last session summary (Markdown rendered)
"View Previous Session" link

Quick Launch Buttons (Large, Primary)

Launch Combat Tracker → Opens /combat-tracker with session context
Roll on Random Table → Opens random tables page or modal picker
Add Session Note → Quick note modal (appends to session GM notes)

Pinned NPCs Feature
Storage:

Option A: Store in Flask session (resets per browser session)
Option B: New field on Session model: pinned_npc_ids (JSON array)

Decision: Use Option B — persist pinned NPCs with the session record.
Update Session Model:
pythonclass Session(db.Model):
    # Existing fields...
    pinned_npc_ids = db.Column(db.JSON)  # Array of NPC IDs
    active_location_id = db.Column(db.Integer, db.ForeignKey('location.id'))
    
    # Relationships
    active_location = db.relationship('Location')
UI for Managing Pinned NPCs:

Button: "Manage Pinned NPCs" opens modal
Modal shows checklist of all NPCs in campaign
Check to pin, uncheck to unpin
Save updates pinned_npc_ids field

Active Location Selection
UI:

Dropdown in Session Mode Dashboard
Shows all locations in campaign
On selection, updates active_location_id on current session
Display location description below dropdown


Part 5: Migrations & Database Updates
New Tables to Create

player_character
campaign_stat_template
player_character_stat
session_attendance
random_table
table_row

Updated Tables
Campaign Model:

No schema changes, but relationships update

Session Model:

Add pinned_npc_ids (JSON)
Add active_location_id (FK to Location)

Migration Strategy
Since we're using db.create_all() (not Flask-Migrate yet), we need manual migration:
Option A: Drop and recreate database (data loss)

Only viable if no production data

Option B: Manually add tables with SQL

Write ALTER TABLE statements
Run via SQLite CLI or Python script

Option C: Finally adopt Flask-Migrate

Initialize Flask-Migrate
Generate initial migration from current state
Add Phase 5 changes as new migration

Recommendation: This is a good time to adopt Flask-Migrate (Phase 5 adds significant schema changes). Here's how:
Adding Flask-Migrate

Install:

bash   pip3 install flask-migrate

Update app.py:

python   from flask_migrate import Migrate
   
   migrate = Migrate(app, db)

Initialize:

bash   flask db init

Create initial migration:

bash   flask db migrate -m "Initial migration with Phase 1-4 models"
   flask db upgrade

Add Phase 5 models, then:

bash   flask db migrate -m "Add Phase 5: Player Characters, Combat, Random Tables"
   flask db upgrade
Do this BEFORE starting Phase 5 development so you can iterate cleanly.

Git Branch Strategy
Each major component gets its own feature branch:

feature/player-characters — PC CRUD, stat template, session attendance
feature/combat-tracker — Ephemeral combat tool
feature/random-tables-custom — Custom table CRUD and roll logic
feature/random-tables-builtin — Built-in tables seed data
feature/session-mode-dashboard — Live play focused view

Merge order:

Player Characters first (other features depend on it)
Combat Tracker and Random Tables can be parallel
Session Mode last (integrates everything)


Build Sequence (Step-by-Step)
Step 0: Adopt Flask-Migrate (Do First!)
Goal: Set up Flask-Migrate so we can manage schema changes cleanly.
Tasks:

Install flask-migrate
Initialize migrations folder
Create baseline migration for existing Phase 1-4 models
Test upgrade/downgrade
Commit to main

Validation:

flask db upgrade works
flask db downgrade works
Database schema unchanged


Step 1: Campaign Stat Template System
Branch: feature/player-characters
Goal: Add stat template preset selection to campaign creation.
Tasks:

Update Campaign model:

Add relationship to CampaignStatTemplate


Create CampaignStatTemplate model:

Fields: campaign_id, stat_name, display_order


Define STAT_PRESETS dict:

Hardcode D&D 5e, Pathfinder 2e, ICRPG, Custom presets


Update campaign create form:

Add preset dropdown
Show preset stats preview
On submit, create template fields based on selection


Add "Manage Stat Template" to campaign settings:

List current template fields
Inline edit stat names
Add/delete fields
Reorder fields (up/down buttons)


Create migration:

bash   flask db migrate -m "Add campaign stat template system"
   flask db upgrade
Validation:

Create new campaign, select "D&D 5e" → template fields created
Edit template in campaign settings → fields update
Delete template field → no errors


Step 2: Player Character CRUD
Branch: feature/player-characters (continue)
Goal: Full CRUD for Player Characters with stat values.
Tasks:

Create PlayerCharacter model:

Fields: character_name, player_name, level_or_rank, class_or_role, status, notes, portrait_filename
Relationship to Campaign


Create PlayerCharacterStat model:

Fields: character_id, template_field_id, stat_value
Relationships to PC and template field


Create PC list page (/pcs):

Query all PCs for active campaign
Display table/cards with filters by status
"Create New PC" button


Create PC detail page (/pcs/<id>):

Show all PC info
Display stats in grid
Render Markdown notes
Edit/Delete buttons


Create PC create/edit form:

Basic info fields
Stat value inputs: Loop through campaign's template fields, create input per stat
Portrait upload (reuse Phase 4 pattern)
On save, create/update PlayerCharacterStat rows


Add PC delete route with confirmation
Create migration:

bash   flask db migrate -m "Add PlayerCharacter and PlayerCharacterStat models"
   flask db upgrade
Validation:

Create PC with stats → values saved correctly
Edit PC stats → updates reflected
Delete PC → stats cascade delete
Change campaign stat template → existing PCs get new blank stat fields


Step 3: Session Attendance Tracking
Branch: feature/player-characters (continue)
Goal: Track which PCs attended which sessions.
Tasks:

Create SessionAttendance model:

Many-to-many between Session and PlayerCharacter


Update Session model:

Add pinned_npc_ids JSON field
Add active_location_id FK
Relationships to PCs via attendance


Update Session edit page:

Add "Player Attendance" section
Checklist of active PCs
On save, update SessionAttendance records


Update Session detail page:

Show list of attending PCs
Display portraits and names


Create migration:

bash   flask db migrate -m "Add session attendance and session mode fields"
   flask db upgrade
Validation:

Edit session, mark PCs as attended → attendance saved
Session detail shows correct PCs
Delete PC → attendance records cascade delete

Merge: PR feature/player-characters to main

Step 4: Combat Tracker (Session Storage)
Branch: feature/combat-tracker
Goal: Ephemeral combat management tool with initiative, HP, status effects.
Tasks:

Create route /combat-tracker:

Renders combat UI template


Build combat tracker template:

Round counter, Next Turn button, End Combat button
Initiative order list (combatants)
Add Combatant form
Monster stat block panel (collapsible textarea)


Write JavaScript for session storage:

combatState object structure
CRUD functions: add/remove/update combatants
Turn/round management
Status effect toggles
HP editing


Auto-populate PCs from session context:

If session['current_session_id'] exists:

Query attending PCs
Show "Add All PCs" button
On click, create combatant entries with PC stats




Add status effect checkboxes per combatant
Test on mobile/tablet viewport

Validation:

Add combatants → appear in initiative order
Update HP → reflected immediately
Next Turn → highlights current combatant
End Combat → clears session storage
Auto-add PCs from session → pre-fills names and stats

Merge: PR feature/combat-tracker to main

Step 5: Random Tables — Custom Tables
Branch: feature/random-tables-custom
Goal: Per-campaign custom random tables with roll logic.
Tasks:

Create RandomTable model:

Fields: campaign_id, name, category, description, is_builtin


Create TableRow model:

Fields: table_id, content, weight, display_order


Create table list page (/random-tables):

Show custom tables for active campaign
"Create New Table" button
Category filter, tabs (All/Custom/Built-in)


Create table detail page:

Show all rows
"Roll on This Table" button
Add/Edit/Delete rows (for custom tables)


Create table CRUD forms:

Create/edit table (name, category, description)
Add/edit row (content, weight)


Implement roll logic:

Route: /random-tables/<id>/roll
Weighted random selection algorithm
Return JSON result
Display in modal


Create migration:

bash   flask db migrate -m "Add RandomTable and TableRow models"
   flask db upgrade
Validation:

Create custom table → saved to campaign
Add rows with weights → rolls respect probability
Roll on table → random result displayed
Delete table → rows cascade delete

Merge: PR feature/random-tables-custom to main

Step 6: Random Tables — Built-in Tables
Branch: feature/random-tables-builtin
Goal: Seed generic built-in tables available to all campaigns.
Tasks:

Create seed data migration:

Define built-in tables (NPC names, weather, tavern names, dungeon features, encounters)
Insert with is_builtin=True, campaign_id=NULL


Update table list page:

Show built-in tables in separate tab
Built-in tables have no Edit/Delete buttons


Test rolling on built-in tables
Create migration:

bash   flask db migrate -m "Seed built-in random tables"
   flask db upgrade
Validation:

All campaigns can access built-in tables
Cannot edit/delete built-in tables
Roll on built-in table → works correctly

Merge: PR feature/random-tables-builtin to main

Step 7: Session Mode Dashboard
Branch: feature/session-mode-dashboard
Goal: Focused live-play view integrating all Phase 5 features.
Tasks:

Create route /session-mode:

Main dashboard template


Session selection UI:

Dropdown of recent sessions
Store selected session in Flask session: session['current_session_id']
On change, reload page


Dashboard layout:

Active Quests: Query quests with status="Active"
Active Location: Dropdown to set, display location description
Pinned NPCs: Display pinned NPCs for current session
Last Session Summary: Fetch previous session, render summary
Quick Launch Buttons: Combat Tracker, Random Tables, Add Note


Pinned NPCs management:

"Manage Pinned NPCs" button opens modal
Checklist of all NPCs
Save updates Session.pinned_npc_ids


Active Location selector:

Dropdown of all locations
Save to Session.active_location_id


Quick note modal:

Textarea input
Appends to Session.gm_notes field


Mobile optimization:

Stack columns on small screens
Large touch targets on buttons



Validation:

Select session → context saved, page updates
Pin NPCs → reflected in dashboard
Set active location → description displayed
Launch Combat Tracker → PCs auto-populated
Roll on Random Table → modal opens

Merge: PR feature/session-mode-dashboard to main

Testing Checklist
Player Characters

 Create campaign with D&D 5e preset → correct stat fields created
 Create PC with stats → values saved
 Edit PC stats → updates reflected
 Mark PC as Dead → status badge shows correctly
 Delete PC → cascade deletes stats and attendance
 Add stat field to campaign template → existing PCs get blank field
 Delete stat field → cascade deletes PC stat values

Session Attendance

 Mark PCs as attended on session → saved correctly
 Session detail shows attending PCs
 Delete PC → attendance records removed

Combat Tracker

 Add combatant manually → appears in list
 Auto-add PCs from session → pre-fills correctly
 Update HP → reflected immediately
 Toggle status effects → checkboxes work
 Next Turn → highlights correct combatant
 Advance round → round counter increments
 End Combat → clears all data
 Browser refresh → data persists (sessionStorage)
 Close browser → data cleared (sessionStorage behavior)

Random Tables

 Create custom table → saved to campaign
 Add rows with weights → saved
 Roll on table → random result respects weights
 Roll 100 times → probability distribution looks correct
 Delete table → rows cascade delete
 Built-in tables visible to all campaigns
 Cannot edit/delete built-in tables

Session Mode Dashboard

 Select session → context saved
 Active quests displayed correctly
 Pin NPCs → reflected in dashboard
 Set active location → description shown
 Launch Combat Tracker → PCs auto-added
 Open Random Tables → works
 Add quick note → appends to session
 Mobile viewport → layout stacks correctly


Future Enhancements (Not Phase 5)
These are good ideas but out of scope for Phase 5:

Combat Tracker: Save encounter to session record as history
Random Tables: Entity linking (roll random NPC from campaign)
Random Tables: User-defined system presets (save custom templates)
Session Mode: Multi-session view (compare sessions side-by-side)
Player Characters: Import from character sheet apps (D&D Beyond, etc.)
Player Characters: XP/Level tracking with history
Combat Tracker: Damage history log per combatant


Summary
Phase 5 delivers:
✅ Player Character tracking with flexible stat system
✅ Campaign stat template presets (D&D 5e, Pathfinder, ICRPG, Custom)
✅ Session attendance tracking
✅ Ephemeral Combat Tracker with initiative, HP, status effects
✅ Custom per-campaign random tables with weighted rolls
✅ Built-in generic random tables
✅ Session Mode Dashboard for live play
Tech additions:
✅ Flask-Migrate for database migrations
✅ JavaScript session storage for ephemeral combat state
✅ Enhanced session context management
After Phase 5:

GM Wiki is a fully functional live table tool
Ready for Phase 6: Player wiki view and Docker deployment
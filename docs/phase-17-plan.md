# Phase 17: AI Campaign Genesis

## Context

The War Table has powerful individual AI tools — generate an NPC, smart-fill a location, brainstorm arc ideas — but no orchestrated workflow connecting them. For a GM (especially one with ADHD), the mental load of jumping between 6 screens, creating things in the right order, and tracking what connects to what is exactly where the app breaks down.

The goal of Phase 17 is to add a **Campaign Genesis Pipeline**: a guided, AI-orchestrated flow that takes a seed idea and builds out a fully-linked Story Arc with all its NPCs, Locations, Quests, Items, and Encounters — automatically, in sequence, with GM approval at each stage.

The pre-session creation pipeline is the missing piece. The during-session (Session Mode Dashboard) and post-session (wrap-up/carryover) workflows already work well once content exists. Phase 17 fills the gap before those flows start.

---

## Approach

### Approval Model: Hybrid (Bundle per Stage)
AI generates the Story Arc structure → GM reviews and edits → AI proposes the full entity bundle → GM checks/unchecks → AI generates all approved entities with arc context. Nothing is saved until the GM approves each stage.

### Seed Input: Free Text + Optional Guided Prompts
A prominent textarea for a free-text premise, with an "Or guide me" accordion that asks specific questions (villain, location, hook, stakes). Both feed the same AI call.

---

## Feature 1: Story Arc Genesis Wizard (Core Feature)

Replace the current basic "create story arc" form with a 4-step guided wizard.

**Entry point:** A new "Create with AI" button on the Story Arcs list page (`/sites`), alongside the existing "New Story Arc" link (which keeps the old form as a fallback for non-AI users).

### Step 1 — The Seed
- Large textarea: "Describe your story arc idea (a sentence or two is fine)"
- Accordion below: "Or answer these questions instead" — fields for: central conflict, villain/antagonist, primary location, player hook, stakes
- "Generate Story Arc →" button calls new AI endpoint

### Step 2 — Review the Arc Structure
- AI returns: Title, Subtitle, Premise, Hook, Themes, Estimated Sessions, 5-7 Milestones
- All fields shown as editable inputs (pre-filled by AI)
- GM edits anything they want
- "Looks good — propose entities →" button

### Step 3 — Approve the Entity Bundle
- AI analyzes the arc content and proposes a bundle:
  - **NPCs**: Villain, key ally, neutral contact, 1-2 minor characters — each with role and one-sentence description
  - **Locations**: Primary location, 1-2 secondary locations — each with type and description
  - **Quests**: Main quest, 1-2 side quests — each with hook
  - **Items**: 1-2 key items (optional, collapsed by default)
  - **Encounters**: 1-2 suggested encounters (optional, collapsed by default)
- Each proposed entity is a card with a checkbox (checked by default), editable name, and visible description
- GM unchecks anything they don't want, edits names/notes
- "Generate all checked entities →" button

### Step 4 — Generation Progress
- Progress bar showing entities being created one by one (NPCs first, then locations, quests, items)
- Each entity appears in a list as it's created, with a link to its detail page
- Uses the existing `/api/ai/generate-entry` endpoint in a sequential loop from the frontend
- All generated entities are automatically linked to this Story Arc via `story_arc_id` FK
- On completion: "Your story arc is ready" summary with links to the arc and all created entities

---

## Feature 2: Campaign Quick-Start

On the existing campaign creation wizard (Step 2 — World Context), after saving the campaign, show a prompt:

> "Your campaign is set up. Want to create your first Story Arc with AI?"

Two buttons: "Create Story Arc →" (launches genesis wizard) and "I'll do it later" (goes to dashboard).

This connects the existing campaign creation wizard to the new arc genesis flow without changing the campaign wizard itself.

---

## Feature 3: Story Arc Entity Hub

Add a **"Linked Entities"** section to the Story Arc detail page (`/sites/<id>`), below the existing content/milestones area.

Shows all entities where `story_arc_id = this arc`:
- Grouped tabs: NPCs | Locations | Quests | Items
- Each entity as a row with name, status badge, and link to its detail page
- "Add existing [NPC/Location/Quest]" dropdown to manually link entities after the fact

---

## Feature 4: Entity-Arc Linking (Database)

Add a nullable `story_arc_id` foreign key to:
- `NPC` model
- `Location` model
- `Quest` model
- `Item` model

This represents an entity's "home arc" — the arc it was created for or primarily belongs to. Entities can still appear in other arcs via shortcodes in Markdown content (the existing system).

On each entity detail page, show a small badge: "Story Arc: [Name]" if `story_arc_id` is set.

**Migration:** One new migration file touching all four tables.

---

## Feature 5: Arc-Aware AI on Entity Detail Pages

When an NPC, Location, Quest, or Item has a `story_arc_id` set, its **Smart Fill** and **Generate Entry** AI calls should automatically include both the campaign world context *and* the story arc's content/premise as additional context. This means AI-generated content always stays coherent with the arc — the villain's personality makes sense for the arc's tone, the location's details fit the arc's stakes, etc.

**How it works:**
- Entity detail pages already call `/api/ai/smart-fill` and `/api/ai/generate-entry`
- When `story_arc_id` is set on the entity, pass it as an optional parameter in those calls
- Both endpoints already accept a `context` field for extra context — extend this to pull the story arc's name + premise when `story_arc_id` is provided
- Show a small "AI has story arc context" indicator near the Smart Fill / Generate buttons when the entity is linked to an arc

This means a GM can generate a rough NPC in the wizard, then come back a week later and hit "Generate Entry" to flesh it out — and the AI will still know it's the villain of a corrupt merchant guild story arc, not just a random character.

---

## New Technical Components

### New Routes (in `app/routes/adventure_sites.py`)
- `GET /sites/genesis` — wizard landing page (serves the 4-step wizard template)
- `POST /sites/genesis/create` — final save: creates the AdventureSite record with all wizard data

### New AI Endpoints (in `app/routes/ai.py`)
- `POST /api/ai/generate-arc-structure` — takes `seed_text` (and optional guided field answers), returns JSON: `{title, subtitle, premise, hook, themes, estimated_sessions, milestones[]}`
- `POST /api/ai/propose-arc-entities` — takes arc content/premise, returns JSON: `{npcs: [{name, role, description}], locations: [{name, type, description}], quests: [{name, hook}], items: [{name, description}], encounters: [{name, description}]}`

### Reused Existing Endpoints
- `POST /api/ai/generate-entry` — already handles NPC, Location, Quest, Item with world context. The genesis wizard calls this in a sequential loop for each approved entity, passing the arc content as additional context.

### New Templates
- `app/templates/adventure_sites/genesis_wizard.html` — the 4-step wizard, using Bootstrap 5 accordion/progress patterns consistent with the existing campaign creation wizard (`campaigns/create.html`)

### Modified Templates
- `app/templates/adventure_sites/detail.html` — add Linked Entities section with tabs
- `app/templates/adventure_sites/index.html` — add "Create with AI" button
- `app/templates/campaigns/create.html` — add post-save prompt on Step 3 completion
- `app/templates/npcs/detail.html`, `locations/detail.html`, `quests/detail.html`, `items/detail.html` — show "Story Arc" badge; pass `story_arc_id` to Smart Fill / Generate calls; show "AI has arc context" indicator

### New JavaScript
- `app/static/js/genesis_wizard.js` — manages step transitions, AI calls, bundle checkbox state, sequential entity generation loop with progress tracking

### Critical Files to Modify
- `app/models.py` — add `story_arc_id` FK to NPC, Location, Quest, Item
- `app/routes/ai.py` — add `generate-arc-structure` and `propose-arc-entities` endpoints
- `app/routes/adventure_sites.py` — add genesis route and create-from-wizard route
- `app/routes/npcs.py`, `locations.py`, `quests.py`, `items.py` — show "Story Arc" badge on detail pages
- New migration file in `migrations/versions/`

### AI Prompt Design
Both new AI endpoints receive the campaign's `ai_world_context` for consistency. The `propose-arc-entities` prompt instructs the AI to propose only entities that are *narratively necessary* for the arc — not an exhaustive list, keeping it focused and manageable.

---

## Pre/During/Post Session Connection

- **Pre-session (Phase 17)**: Genesis Wizard → Story Arc Entity Hub → entity detail editing
- **During session**: Session Mode Dashboard already displays Story Arc content with sticky ToC (Phase 15a — complete)
- **Post-session**: Post-session wrap-up and carryover already work (Phase 12 — complete)

Phase 17 completes the loop.

---

## Verification / Testing

1. Run `python3 run.py` from `gm-wiki/`
2. Create a new campaign with AI world context set
3. Navigate to Story Arcs → "Create with AI"
4. Enter a seed idea (e.g. "A corrupt merchant guild is secretly funding a bandit army to destabilize the northern trade routes")
5. Verify Step 2 returns a complete arc structure with editable fields
6. Verify Step 3 proposes a sensible bundle of ~8-12 entities with checkboxes
7. Uncheck one or two entities, then click generate
8. Verify all checked entities are created and appear in the database with `story_arc_id` set
9. Verify the Story Arc detail page shows a "Linked Entities" section with all created entities
10. Open one generated NPC — verify it shows "Story Arc: [Name]" badge
11. Run `FLASK_APP=run.py python3 -m flask db upgrade` to confirm migration applies cleanly

---

## Phase 17 Feature Table

| Feature | Status | Notes |
|---------|--------|-------|
| Entity-Arc FK (story_arc_id) | TODO | Migration required; nullable on NPC, Location, Quest, Item |
| generate-arc-structure AI endpoint | TODO | New; takes seed text, returns arc JSON |
| propose-arc-entities AI endpoint | TODO | New; takes arc content, returns entity bundle JSON |
| Story Arc Genesis Wizard (4-step) | TODO | New template + JS; reuses existing generate-entry endpoint for batch creation |
| Campaign Quick-Start prompt | TODO | Minor addition to campaigns/create.html Step 3 |
| Story Arc Entity Hub | TODO | New section on adventure_sites/detail.html |
| Entity "Story Arc" badge | TODO | Small addition to NPC/Location/Quest/Item detail pages |
| Arc-aware AI on entity pages | TODO | Smart Fill + Generate Entry pass story arc context when entity has story_arc_id |

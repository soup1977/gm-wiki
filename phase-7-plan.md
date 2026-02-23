# GM Wiki — Phase 7: Smart Import & AI Content Population

## Overview

Phase 7 adds two ways to populate your GM Wiki faster:

1. **Open5e Bestiary Import** — Search and import SRD creatures directly from the web (no AI key needed)
2. **AI Smart Fill** — Paste raw text into any create form and Claude pre-fills the fields for you

Neither feature is required to use GM Wiki — they're both optional accelerators. Smart Fill gracefully disables itself when no API key is configured.

---

## Why These Features?

Right now, populating GM Wiki from scratch is manual: type every NPC, location, and session entry by hand. These features cut that work significantly:

- **Bestiary**: Instead of manually typing goblin stats you've used a hundred times, search Open5e and import them in two clicks.
- **Smart Fill**: Instead of carefully copying session notes into the right fields, paste your raw notes and let the AI draft the entry. You review and save.

---

## Part 1: Open5e Bestiary Import

### What is Open5e?

Open5e is a free, public REST API that serves 5th Edition SRD content. No authentication, no cost, no account needed. It covers hundreds of creatures from the core SRD.

**Example API call:**
```
GET https://api.open5e.com/v1/monsters/?search=goblin&limit=10
```

Returns structured JSON: name, CR, size, type, ability scores, actions, traits, etc.

### User Flow

1. Go to **Bestiary** → click **"Import from Web"**
2. Search box: type a creature name (e.g., "goblin")
3. Results list appears with name, CR, type
4. Click a result → preview panel shows the full stat block as it will appear
5. Click **"Add to Bestiary"** → creature is imported as a `BestiaryEntry`
6. Redirects to the new bestiary entry for review/edit

### How We Map Open5e Data to BestiaryEntry

| Open5e Field              | BestiaryEntry Field     | Notes                                       |
|---------------------------|-------------------------|---------------------------------------------|
| `name`                    | `name`                  | Direct                                      |
| `cr`                      | `cr_level`              | Prefixed: "1/4" → "CR 1/4"                 |
| `type`, `size`            | `tags`                  | e.g., "humanoid, small"                    |
| Full stat block (built)   | `stat_block`            | Formatted as Markdown (see below)           |
| `document__title`         | `source`                | e.g., "5e SRD" or "Open5e"                |
| (hardcoded)               | `system`                | "D&D 5e SRD"                               |

**Stat block Markdown format** (assembled from multiple Open5e fields):

```markdown
*Size Type, Alignment*

**Armor Class** 15 (natural armor)
**Hit Points** 7 (2d6)
**Speed** 30 ft.

| STR | DEX | CON | INT | WIS | CHA |
|-----|-----|-----|-----|-----|-----|
| 8 (-1) | 14 (+2) | 10 (+0) | 10 (+0) | 8 (-1) | 8 (-1) |

**Skills** Stealth +6
**Senses** Darkvision 60 ft., passive Perception 9
**Languages** Common, Goblin
**Challenge** 1/4 (50 XP)

---

**Nimble Escape.** The goblin can take the Disengage or Hide action as a bonus action.

### Actions

**Scimitar.** *Melee Weapon Attack:* +4 to hit, reach 5 ft., one target. *Hit:* 5 (1d6 + 2) slashing damage.
```

### New Files

- `app/routes/bestiary_import.py` — new Blueprint for the import feature
- `app/templates/bestiary/import_web.html` — search + preview UI
- `app/static/js/bestiary_import.js` — JS for live search (fetch API, debounced)

### Route Structure

| Route                           | Method     | Purpose                                      |
|---------------------------------|------------|----------------------------------------------|
| `/bestiary/import/web`          | GET        | Import page (search form)                    |
| `/bestiary/import/web/search`   | GET (AJAX) | Proxy to Open5e API, returns JSON results    |
| `/bestiary/import/web/preview`  | GET (AJAX) | Full detail for one creature (stat block)    |
| `/bestiary/import/web/save`     | POST       | Creates the BestiaryEntry in DB              |

**Why proxy through Flask instead of calling Open5e directly from JS?**
Because calling external APIs from browser JS can have CORS issues, and proxying through Flask gives us control over rate limiting and error handling if the API is down.

### Duplicate Handling

Before importing, check if a BestiaryEntry with the same name already exists. If it does, show a warning: "A creature named 'Goblin' already exists. Import anyway?" with options to cancel or proceed (which creates a second entry).

---

## Part 2: AI Smart Fill (Claude API)

### What It Does

Every create/edit form for NPCs, Locations, Quests, Items, and Sessions gets a "Smart Fill" button. Clicking it opens a text area where you paste any raw text — handwritten notes, a description from a forum post, session recap you typed on your phone. The AI reads it and fills in the form fields. You review and save (or edit first).

### Claude API — Plain English Explanation

The Claude API works like this: you send text to Anthropic's servers, Claude reads it and responds. You pay a small fee per amount of text processed (a typical Smart Fill would cost well under $0.01). You need an API key from Anthropic to authenticate.

**Setup:**
1. Go to `console.anthropic.com` and create an API key
2. Add it to your `.env` file (or docker-compose.yml env vars): `ANTHROPIC_API_KEY=sk-ant-...`
3. The app detects the key and enables Smart Fill features

If no key is configured, Smart Fill buttons are hidden (or shown as greyed out with a "Configure API key" tooltip). The rest of the app is completely unaffected.

### New Python Dependency

```
anthropic>=0.40
```

Added to `requirements.txt`.

### User Flow

1. On any entity **create** or **edit** form, click the **"Smart Fill"** button
2. A modal appears with a large text area and a prompt: "Paste notes about this [NPC/Location/etc.]"
3. You paste your text and click **"Fill Fields"**
4. Spinner while Claude processes (~2-5 seconds)
5. Modal closes, form fields are pre-filled with extracted content
6. Review the fields — edit anything the AI got wrong
7. Submit the form normally

**The AI does not save anything.** It only fills in the form. You still click Save.

### What the AI Extracts Per Entity Type

**NPC:**
- name, role, status (alive/dead/unknown), faction
- physical_description, personality, secrets, notes
- Tags (suggested)

**Location:**
- name, type, description, gm_notes
- Tags (suggested)

**Quest:**
- name, status (active/completed/failed), hook, description, outcome, gm_notes
- Tags (suggested)

**Item:**
- name, type, rarity (common/uncommon/rare/very rare/legendary/unique), description, gm_notes
- Tags (suggested)

**Session:**
- number (if detectable), title, summary, gm_notes
- date_played (if mentioned)

For fields the AI can't detect from the text, it returns `null` and those fields stay blank.

### Technical Implementation

**New route file: `app/routes/ai.py`**

A Flask Blueprint registered at `/api/ai/`. It handles one endpoint:

```
POST /api/ai/smart-fill
Body: { "entity_type": "npc", "text": "Borin is a heavyset dwarf who runs..." }
Returns: { "name": "Borin", "role": "innkeeper", "status": "alive", ... }
```

This is a JSON API endpoint — the form page calls it via JavaScript `fetch()`, gets back JSON, and uses it to populate the form fields.

**Prompt structure:**

Each entity type has its own system prompt that tells Claude:
- What entity type this is
- What fields to extract (with valid values for constrained fields like `status`)
- That it must return valid JSON matching the schema
- To leave fields `null` if not detectable rather than guessing

**Frontend: `app/static/js/smart_fill.js`**

One shared JS file handles the Smart Fill modal across all form pages:
- Handles the button click → modal open
- Sends `fetch()` POST to `/api/ai/smart-fill`
- On success: maps JSON response keys to form field `name` attributes and sets values
- On error: shows error message in modal (API key missing, network error, Claude error)

### Settings Page

New route: `/settings/`

A simple page that shows:
- **Claude API Status:** Connected (model: claude-sonnet-4-6) / Not configured
- Link: "Get an API key at console.anthropic.com"
- A "Test Connection" button that sends a minimal API call and shows success/failure
- **App Info:** version, database stats (number of campaigns, entities, etc.)

This is also the right place for future settings (if we ever add them).

**New files:**
- `app/routes/settings.py`
- `app/templates/settings/index.html`

**Navbar:** Add "Settings" link to the GM navbar (gear icon, bottom of sidebar or in the top bar).

---

## Part 3: Build Sequence

### Step 1: Open5e Bestiary Import
**Branch:** `feature/open5e-import`

1. Create `app/routes/bestiary_import.py` Blueprint
2. Register Blueprint in `app/__init__.py`
3. Write the Flask proxy routes (`/search`, `/preview`, `/save`)
4. Write `stat_block` Markdown formatter from Open5e JSON
5. Create `app/templates/bestiary/import_web.html`
6. Write `app/static/js/bestiary_import.js` (live search, preview pane)
7. Add "Import from Web" button to the Bestiary index page
8. Test: search "goblin", import, verify BestiaryEntry record
9. Test: duplicate handling

**No migration needed** — uses existing BestiaryEntry model.

### Step 2: Settings Page + Claude API Config
**Branch:** `feature/ai-smart-fill`

1. Add `anthropic` to `requirements.txt`
2. Update `config.py` to read `ANTHROPIC_API_KEY` from environment
3. Create `app/routes/settings.py` and register Blueprint
4. Create `app/templates/settings/index.html`
5. Add Settings link to navbar
6. Test: page loads, API status shows correctly when key is/isn't set

### Step 3: Smart Fill — NPC Form (Prototype)
*(Continue on `feature/ai-smart-fill`)*

7. Create `app/routes/ai.py` with the `/api/ai/smart-fill` endpoint
8. Write the NPC extraction prompt + Claude API call + JSON parsing
9. Create `app/static/js/smart_fill.js`
10. Add Smart Fill button + modal to NPC create form
11. Test end-to-end: paste NPC text → fields pre-filled correctly

### Step 4: Smart Fill — Remaining Forms
*(Continue on `feature/ai-smart-fill`)*

12. Add extraction prompts for Location, Quest, Item, Session
13. Add Smart Fill button + modal to each create form
14. Test each entity type
15. Test graceful degradation: remove API key → buttons hidden/disabled

---

## New Files Summary

```
app/
├── routes/
│   ├── bestiary_import.py   # Open5e proxy + import logic
│   ├── ai.py                # /api/ai/smart-fill endpoint
│   └── settings.py          # Settings page
├── templates/
│   ├── bestiary/
│   │   └── import_web.html  # Open5e search + preview UI
│   └── settings/
│       └── index.html       # Settings page
└── static/
    └── js/
        ├── bestiary_import.js   # Live search and preview for Open5e
        └── smart_fill.js        # Smart Fill modal + form population
```

**No new database models.** No migrations required.

---

## Configuration

### Environment Variables Added

| Variable             | Required For        | Where to Set                   |
|----------------------|---------------------|--------------------------------|
| `ANTHROPIC_API_KEY`  | Smart Fill          | `.env` file or docker-compose  |

The Open5e import requires no environment variables.

### Updating `config.py`

```python
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
AI_ENABLED = bool(os.environ.get('ANTHROPIC_API_KEY'))
```

### Updating `docker-compose.yml`

```yaml
environment:
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}   # Optional — enables Smart Fill
```

---

## Testing Checklist

### Open5e Bestiary Import
- [ ] Search returns results for "goblin", "dragon", "skeleton"
- [ ] Results show name, CR, type in a clean list
- [ ] Preview panel renders the full formatted stat block
- [ ] Import creates a valid BestiaryEntry record
- [ ] Imported entry appears in the Bestiary list
- [ ] Duplicate warning appears if name already exists
- [ ] "Import from Web" button is visible on Bestiary index page

### AI Smart Fill
- [ ] With no `ANTHROPIC_API_KEY` set: Smart Fill button is not shown (or greyed out)
- [ ] Settings page correctly shows "Not configured" when key is missing
- [ ] Settings page shows "Connected" when key is valid
- [ ] "Test Connection" button returns success/failure
- [ ] NPC: paste text → name, role, personality fields pre-filled
- [ ] Location: paste text → name, type, description pre-filled
- [ ] Quest: paste text → name, hook, description pre-filled
- [ ] Item: paste text → name, type, rarity pre-filled
- [ ] Session: paste text → title, summary pre-filled
- [ ] Fields with constrained values (status, rarity) only get valid values
- [ ] Fields not detectable in text are left blank (not hallucinated)
- [ ] API error returns a user-friendly message in the modal
- [ ] Network error (Claude API down) fails gracefully

---

## Git Branch Strategy

```
feature/open5e-import    → Part 1: Bestiary web import
feature/ai-smart-fill    → Part 2: Settings page + Claude API + Smart Fill
```

**Suggested commits:**
1. "Add Open5e proxy routes and stat block formatter"
2. "Add Bestiary web import UI and live search"
3. "Add Settings page and Claude API config"
4. "Add AI Smart Fill endpoint and NPC form integration"
5. "Extend Smart Fill to Location, Quest, Item, Session forms"

---

## Future: Phase 8 — Obsidian Vault Import

This was discussed but deferred due to complexity. The Obsidian import would:
- Accept a .zip upload of a vault
- Parse all `.md` files (YAML frontmatter + body)
- Use AI to classify each note as NPC/Location/Quest/etc.
- Show a preview table for GM review before importing
- Resolve `[[WikiLinks]]` into entity relationships by name-matching

**Why it's Phase 8, not 7:** The Phase 7 features are self-contained and easy to verify. Obsidian import requires handling many vault structures, resolving cross-references in the right order, and building a robust preview/confirmation step. It deserves its own dedicated phase.

---

## Summary

Phase 7 delivers:

✅ Open5e Bestiary Import — search and import SRD creatures, no API key needed
✅ AI Smart Fill — Claude-powered form pre-fill from raw text (NPC, Location, Quest, Item, Session)
✅ Settings page — API status, test connection, app info
✅ No new database models — fully additive to existing schema
✅ Graceful degradation — Smart Fill is hidden when no API key is configured

After Phase 7, you can go from "empty bestiary" to "100 creatures imported" in minutes, and from "messy session notes in a phone app" to "clean session entry in GM Wiki" in seconds.

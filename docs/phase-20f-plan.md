# Phase 20f — Runner Right Panel: Full Combat, Tables Tab, Remove Session Mode

## Context

The Adventure Runner's right panel currently has 4 tabs (Combat, Session, NPCs, AI Tools). Three improvements are needed:

1. **Combat tab** is a minimal HP tracker. The full combat tracker (`/combat-tracker`) lives in a separate browser tab with no connection back to the runner. The goal is to make the runner's combat tab a full inline tracker so the GM never needs to leave the runner during a session.

2. **Random Tables** are accessible only from `/random-tables/`, a separate page. Rolling a table mid-encounter requires navigating away. A Tables tab in the runner puts them one click away.

3. **Session Mode** (`/session-mode`) was the old at-table dashboard. All its features are now in the runner's right panel. It should be removed from the navbar — the runner is the replacement.

---

## Right Panel: New 5-Tab Layout

```
╔═════════════════════╗
║ ⚔️ Combat            ║  ← UPGRADED: full inline tracker
║ 📋 Session           ║  ← existing (notes, quests, location)
║ 🧑 NPCs              ║  ← existing (key NPCs + NPC chat)
║ 🎲 AI Tools          ║  ← existing (improv, hazard, consequences)
║ 🎯 Tables            ║  ← NEW: roll random tables inline
╚═════════════════════╝
```

---

## Change 1: Upgrade Combat Tab

### What it gets
- **Round counter + Next Turn button** at the top of the tab
- **Active turn highlighted** (gold border on current combatant)
- **Initiative input** per combatant (editable number field; list auto-sorted high→low)
- **HP controls** — bar + current/max display + [−] [+] buttons (same as now, but with turn context)
- **Status effect badges** — click [+Status] → small preset list (Prone, Poisoned, Stunned, Invisible, etc.) → tag appears on combatant row with [×] to clear
- **Persist across room navigation** via `localStorage` key `'gm_wiki_combat_runner'` so combat state survives clicking into different rooms

### State model (mirrors full tracker)
```javascript
// localStorage key: 'gm_wiki_combat_runner'
{
  round: 1,
  currentTurnIndex: 0,
  combatants: [
    { id, name, initiative, currentHp, maxHp, hearts, ac, statusEffects[] }
  ]
}
```

### addToCombat() change
Currently populates a plain `combatants[]` JS array. Change to read/write the localStorage state object so state persists on room load.

### Persistence
Use `localStorage` key `'gm_wiki_combat_runner'`. Combat state survives room-to-room navigation and page refreshes. Cleared only by the [Clear] button.

### "Full Tracker" link
Keep as a fallback — opens the standalone `/combat-tracker` in a new tab for complex battles. No sync needed.

### Files changed
- `app/templates/adventures/runner.html` — replace combat tab HTML and JS functions (`addToCombat`, `renderCombat`, `adjustHp`, `removeCombatant`, `clearCombat`); add localStorage load/save

---

## Change 2: Add Tables Tab

### What it shows
- Search input at top to filter tables by name
- Tables grouped: **Built-in** (seeded ICRPG/SRD tables) then **Custom** (campaign-created)
- Each table is a button: click → `GET /random-tables/<id>/roll` → result displayed inline below it
- Result shows: rolled text (prominent) + timestamp (small/muted)
- Results persist until next roll (DOM only, no DB needed)

### Route change
Pass `all_tables` to the `run()` template:
```python
# app/routes/adventures.py — run() function
from app.models import RandomTable
all_tables = RandomTable.query.filter_by(campaign_id=campaign.id).order_by(
    RandomTable.is_builtin.desc(), RandomTable.name).all()
```
(Check exact field name for built-in flag; may be `source` or `is_seed`.)

### JS function
```javascript
async function rollTable(tableId, btnEl) {
    const resp = await fetch(`/random-tables/${tableId}/roll`);
    const data = await resp.json();  // {table_name, result, timestamp}
    document.getElementById('table-result-' + tableId).textContent = data.result;
}
```

### Files changed
- `app/templates/adventures/runner.html` — add `#rt-tables` tab pane + `rollTable()` JS
- `app/routes/adventures.py` — pass `all_tables` from `run()`

---

## Change 3: Full Removal of Session Mode

### What gets deleted
- `app/routes/session_mode.py` — entire blueprint file removed
- `app/templates/session_mode/` — all templates deleted
- `app/__init__.py` — remove `session_mode` blueprint import and `register_blueprint` call
- `app/templates/base.html` — remove Session Mode navbar link

### AI endpoints migration
Three endpoints the runner calls must move to `adventures.py` (or a shared blueprint). New URLs:

| Old URL | New URL | Function |
|---|---|---|
| `POST /session-mode/npc-chat` | `POST /adventures/ai/npc-chat` | NPC dialogue generator |
| `POST /session-mode/hazard-flavor` | `POST /adventures/ai/hazard-flavor` | Hazard flavor text |
| `POST /session-mode/suggest-consequences` | `POST /adventures/ai/suggest-consequences` | Ripple consequences |

Runner `fetch()` calls updated to the new URLs.

### Note endpoints migration
Two more endpoints used by the runner's Session tab:

| Old URL | New URL |
|---|---|
| `POST /session-mode/add-note` | `POST /adventures/<id>/runner-note` (already exists) |
| `POST /session-mode/set-location` | `POST /adventures/<id>/runner-location` (already exists) |

Runner already calls the adventure-scoped versions — no JS change needed.

### What the runner already has (replaces session mode for adventure runs)
| Old Session Mode feature | Runner equivalent |
|---|---|
| Quick notes | Session tab → [+ Add Note] |
| Active location | Session tab → location dropdown |
| Active quests | Session tab → quest list |
| NPC Chat | NPCs tab → [Chat] per NPC |
| Hazard Flavor | AI Tools tab |
| Suggest Consequences | AI Tools tab |
| Improv Encounter | AI Tools tab |
| Post-session wrap-up | Session detail page (linked from runner top bar) |

### Files changed
- `app/routes/session_mode.py` — delete file
- `app/templates/session_mode/` — delete folder
- `app/routes/adventures.py` — add 3 migrated AI endpoints
- `app/__init__.py` — remove session_mode blueprint
- `app/templates/base.html` — remove Session Mode navbar `<li>`
- `app/templates/adventures/runner.html` — update 3 fetch() URLs to new adventure routes

---

---

## Change 4: Campaign-Spanning Quest Linking

### Problem
`Quest.adventure_id` is a single FK — a quest "belongs to" one adventure. Campaign-spanning quests (e.g. "Defeat the Overlord") have no `adventure_id` and can't be shown in the runner without a proper link.

### Solution: M-to-M `adventure_quest_link` table
Mirror the existing `adventure_npc_link` pattern. Any campaign-wide quest can be linked to one or more adventures.

```python
# New association table (DB migration required)
adventure_quest_link = db.Table('adventure_quest_link',
    db.Column('adventure_id', db.Integer, db.ForeignKey('adventure.id'), primary_key=True),
    db.Column('quest_id',     db.Integer, db.ForeignKey('quests.id'),    primary_key=True)
)

# New relationship on Adventure model
campaign_quests = db.relationship('Quest', secondary=adventure_quest_link,
                                  backref='linked_adventures')
```

### Scope badge (derived — no new DB field)
Displayed in runner Session tab and adventure detail Quests section:
- `quest.adventure_id == this_adventure.id` → blue badge **[Adventure]**
- `quest.adventure_id is None` (linked via M-to-M) → gold badge **[Campaign]**

### Adventure detail page — Quests section
Add a **Link Quest** button alongside the existing "Link NPC / Link Faction" buttons. Calls the existing `POST /adventures/<id>/link-entity` route with `entity_type=quest`. Displays both adventure-specific and linked campaign quests in the Entities tab.

### Runner Session tab
Pass `campaign_quests = adventure.campaign_quests` from `run()`. Session tab shows combined list (both `adventure.linked_quests` and `adventure.campaign_quests`) with scope badge on each row.

### Files changed
- `app/models.py` — add `adventure_quest_link` table + `Adventure.campaign_quests` relationship
- `migrations/` — new migration for the table
- `app/routes/adventures.py` — update `link_entity` / `unlink_entity` to handle `quest` type; pass `campaign_quests` to `run()`
- `app/templates/adventures/detail.html` — add Quest link/unlink UI in Entities tab
- `app/templates/adventures/runner.html` — Session tab shows both quest lists with scope badges

---

## All Files to Modify

| File | Change |
|---|---|
| `app/templates/adventures/runner.html` | Upgrade combat tab (localStorage, initiative, status effects, round/turn); add Tables tab; update 3 fetch() URLs; Session tab shows both quest lists |
| `app/routes/adventures.py` | Pass `all_tables`, `campaign_quests` to `run()`; add 3 migrated AI endpoints; add quest to link/unlink entity handler |
| `app/models.py` | Add `adventure_quest_link` table + `Adventure.campaign_quests` relationship |
| `app/routes/session_mode.py` | **Delete** |
| `app/templates/session_mode/` | **Delete folder** |
| `app/__init__.py` | Remove session_mode blueprint import/registration |
| `app/templates/base.html` | Remove Session Mode navbar link |
| `app/templates/adventures/detail.html` | Add Quest link/unlink UI in Entities tab |
| `migrations/versions/` | New migration for `adventure_quest_link` table |
| `app/routes/ai.py` | Extend `generate_adventure_skeleton()` prompt to include quests; return in JSON |
| `app/templates/adventures/draft_review.html` | Show AI-generated quest list with checkboxes |
| `app/routes/adventures.py` (`create()`) | Create Quest records for checked quests on adventure confirm |

---

## Change 5: Quest Frameworks in AI Adventure Generation

### Problem
When the AI generates an adventure skeleton from a concept prompt, it creates Acts/Scenes/Rooms but does not create any quests. The GM has to manually build quests after the fact.

### Solution: AI generates quest stubs during adventure creation

**Where it happens:** The existing `POST /ai/generate-adventure` endpoint in `app/routes/ai.py` (the one that takes the concept prompt and returns Acts/Scenes/Rooms JSON). Extend the AI prompt to also return a `quests` array.

**AI prompt addition:**
```
Also generate 2-4 quests that drive the adventure. Each quest should have:
- name: short quest title
- hook: one sentence — how players get involved
- scope: "adventure" (specific to this adventure) or "campaign" (could span beyond)
- status: "Active"
```

**AI response extension:**
```json
{
  "acts": [...],
  "quests": [
    { "name": "Find the Stolen Map", "hook": "A merchant hires the party...", "scope": "adventure" },
    { "name": "Stop the Ritual", "hook": "Time is running out...", "scope": "adventure" },
    { "name": "Unravel the Conspiracy", "hook": "Someone powerful is pulling strings...", "scope": "campaign" }
  ]
}
```

**After adventure creation:** On the draft review page (`draft_review.html`), show the generated quests as a preview list. For each quest:
- **Adventure-scope** quests: checkbox to include → creates a new `Quest` record with `adventure_id` set
- **Campaign-scope** quests: dropdown showing `[Create New]` plus any existing campaign quests that share keywords in the name — allows the GM to link an AI-suggested quest to an already-existing campaign quest instead of duplicating it

The keyword matching is done server-side: the `draft_review` route receives the quest list and queries `Quest.query.filter_by(campaign_id=..., adventure_id=None)` to find candidates, then passes them to the template for display.

**Files changed:**
- `app/routes/ai.py` — extend AI prompt in `generate_adventure_skeleton()` to include quests; return quests in JSON response
- `app/routes/adventures.py` — `draft_review()` GET: pass existing campaign quests for matching; `create()` POST: create or link Quest records based on form choices
- `app/templates/adventures/draft_review.html` — show quest preview with adventure/campaign badges; campaign quests show link-or-create dropdown

---

## Verification

1. Open adventure → Run → 5 tabs visible in right panel
2. **Combat:** Add creature → appears; Next Turn → highlight moves; change initiative → re-sorts; add status badge → appears; navigate rooms → combat state persists (localStorage); refresh page → still there
3. **Tables:** Search filters list; built-in/custom groups visible; click a table → result appears inline
4. **Session Mode:** Link gone from navbar; runner Session/NPC/AI tabs still work (endpoints now at `/adventures/ai/*`)
5. **Quests:** Link a campaign quest to adventure from detail page → appears in runner Session tab with [Campaign] badge; adventure-specific quests show [Adventure] badge
6. **AI Quest Generation:** Create new adventure → draft review shows 2–4 AI-generated quests with checkboxes → approve → Quest records created and linked to adventure

---

---
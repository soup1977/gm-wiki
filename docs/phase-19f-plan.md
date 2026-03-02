# Phase 19f: ICRPG Loot & Ability Mechanics

## Context
The ICRPG loot and ability system has structural gaps: (1) abilities aren't filtered by the character's type/class, (2) spells aren't filtered by casting stat, (3) loot seed data has no structured `effects` JSON — all bonuses are baked into prose descriptions, (4) slot costs default to 1 for everything, and (5) there's no mechanical enforcement of requirements like "DEX rolls HARD" or "can't cast WIS spells."

After a thorough audit of all seed data (~3400 lines across 5 files), the effect types break down into two buckets:

**Mechanically enforceable** (can auto-apply on equip):
- Stat bonuses: `+N STAT` (STR, DEX, CON, INT, WIS, CHA)
- Effort bonuses: `+N EFFORT_TYPE`
- Defense bonuses: `+N DEFENSE`
- Hearts bonuses: `+N HEARTS`
- Slot cost overrides: items that take 0, 2, 3, or 5 slots

**GM-adjudicated** (text reminders only — too varied/conditional to automate):
- "DEX rolls always HARD"
- "immune to fire"
- "sacrifice the shield to absorb all of 1 attack"
- "roll ULTIMATE effort every time"
- "walk on any surface without a check"
- Hundreds of unique one-off effects

**Branch:** `feature/phase-19f-loot-ability-mechanics`

---

## Features

| Feature | Status | Notes |
|---------|--------|-------|
| Parse effects from seed data | Planned | Regex parser script for structured `effects` JSON |
| Filter abilities by character type | Planned | Default to character's type in Add Ability modal |
| Filter spells by casting stat | Planned | INT/WIS dropdown in Add Loot spell tab |
| Slot cost tracking | Planned | Per-item slot_cost, updated totals in model |
| Effect badges on equipped items | Planned | Visual badges showing stat/effort/defense bonuses |
| Total loot bonuses summary | Planned | Summary row below equipped loot |
| Soft requirement warnings | Planned | Warn on cross-type ability add |
| Spell casting stat display | Planned | Show INT/WIS on equipped spells |

---

## File Changes

| File | Action | Summary |
|------|--------|---------|
| `app/seed_data/icrpg_starter_loot.json` | Modify | Add `effects` and `slot_cost` to every entry |
| `app/seed_data/icrpg_loot.json` | Modify | Add `effects` and `slot_cost` to entries with parseable bonuses |
| `app/routes/pcs.py` | Modify | Filter abilities by character's type, filter spells by casting stat |
| `app/static/js/icrpg_sheet.js` | Modify | Client-side type/stat filtering in Add Ability & Add Loot modals |
| `app/templates/pcs/icrpg_sheet.html` | Modify | Show effect badges on equipped loot, display slot cost |
| `app/routes/icrpg_catalog.py` | Modify | Validate effects JSON, support new fields in CRUD |
| `scripts/parse_loot_effects.py` | Create | One-time script to parse effects from seed data descriptions |
| `docs/phase-19f-plan.md` | Create | Phase plan doc |

**No model changes. No new migration.**

---

## Implementation Order

1. Write and run the effects parser script (Part 1)
2. Update seed data with parsed effects + slot costs (Part 1)
3. Smart filtering in modals (Part 2)
4. Slot cost display and calculation (Part 3)
5. Effect badges on equipped items (Part 4)
6. Soft requirement warnings (Part 5)
7. Phase plan doc + CLAUDE.md update

# Phase 19h: Basic World Loot in Character Wizard + Homebrew Support

## Context

Per ICRPG rules, character creation includes **two** loot selections:
1. **1 Type-specific starting loot** (already implemented — wizard step 7)
2. **N Basic world loot picks** from the character's world pool (NOT implemented)

The number of basic loot picks varies by world:
- Alfheim: 4 picks
- Warp Shell: 4 picks
- Ghost Mountain: 3 picks
- Vigilante City: 3 picks
- Blood and Snow: 2 picks

Only Alfheim and Warp Shell currently have basic loot seed data (24 items each). Other worlds will auto-skip the basic loot step until data is added.

The homebrew catalog also needs updates to support marking loot as "basic/starter" and configuring how many picks a world allows.

**Branch:** `feature/basic-world-loot-wizard`

---

## Features

| Feature | Status | Notes |
|---------|--------|-------|
| `basic_loot_count` on ICRPGWorld model | Planned | New column + migration |
| Seed function sets count per builtin world | Planned | Alfheim=4, Warp Shell=4, Ghost Mountain=3, Blood and Snow=2 |
| Catalog serialization includes basic loot per world | Planned | Filters out type-specific loot via ICRPGStartingLoot |
| Wizard step 8: multi-select basic loot picker | Planned | 9-step wizard (was 8) |
| Auto-skip step 8 if no basic loot available | Planned | Ghost Mountain, Blood and Snow skip for now |
| Backend validation + ICRPGCharLoot creation | Planned | Basic loot equipped on character sheet |
| Homebrew catalog: `is_starter` checkbox on loot form | Planned | Mark homebrew loot as available during creation |
| Homebrew catalog: `basic_loot_count` on world form | Planned | Configure picks per homebrew world |
| Starter badge in catalog loot tab | Planned | Visual indicator |

---

## File Changes

| File | Action | Summary |
|------|--------|---------|
| `app/models.py` | Modify | Add `basic_loot_count` to ICRPGWorld |
| `migrations/versions/xxxx_add_basic_loot_count.py` | Create | Migration for new column |
| `app/__init__.py` | Modify | Set `basic_loot_count` per builtin world during seed |
| `app/routes/pcs.py` | Modify | Serialize basic loot, validate picks on create |
| `app/static/js/icrpg_wizard.js` | Modify | Step 8 multi-select picker, bump to 9 steps |
| `app/templates/pcs/icrpg_wizard.html` | Modify | Add step-8 HTML, renumber step-9 |
| `app/routes/icrpg_catalog.py` | Modify | Handle `is_starter` and `basic_loot_count` in CRUD |
| `app/static/js/icrpg_catalog.js` | Modify | Add checkbox and number field to forms |

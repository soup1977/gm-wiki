# Phase 19j: ICRPG Catalog — Friendly JSON Editors + Type Manage Modal

## Context

Three UX improvements to the ICRPG Homebrew Catalog:

1. **JSON fields are unfriendly.** Life Form Bonuses and Loot Effects were raw JSON text boxes requiring users to know key names and syntax. Milestone Path Tiers was an even more complex nested structure.
2. **Description preview missing.** Several catalog tables (Life Forms, Types, Loot) showed no description, making it hard to identify entries at a glance.
3. **Imported Types had no loot management UI.** When a builtin Type was imported, its starting loot was deep-copied but had no UI — you couldn't see, add, or remove starting loot options.

**Branch:** `feature/catalog-json-editors-type-manage`

---

## Features

| Feature | Status | Notes |
|---------|--------|-------|
| Description preview columns on catalog tables | Complete | PR #50 — Life Forms, Types, Loot tables; truncated with tooltip |
| Stat grid for Life Form Bonuses | Complete | Labeled inputs for all stats, effort dice, Defense, Hearts, Innate Ability |
| Stat grid for Loot Effects | Complete | Same as above plus Equip Slots and Carry Slots |
| Tier accordion editor for Milestone Paths | Complete | 4 collapsible tiers, add/remove item rows per tier |
| Type Manage modal | Complete | Gear icon on each homebrew Type; shows abilities + starting loot with full CRUD |
| Backend routes for Type manage | Complete | GET manage, POST starting-loot/add, POST starting-loot/<id>/delete |

---

## Valid Stat Keys

**Life Form Bonuses:** STR, DEX, CON, INT, WIS, CHA, BASIC_EFFORT, WEAPON_EFFORT, GUN_EFFORT, MAGIC_EFFORT, ULTIMATE_EFFORT, HEARTS, DEFENSE, ABILITY (text, not numeric)

**Loot Effects:** Same as above minus ABILITY, plus EQUIPPED_SLOTS, CARRIED_SLOTS

## Tier Structure

```json
{
  "1": [{"name": "Item Name", "description": "What it does"}],
  "2": [...],
  "3": [...],
  "4": [...]
}
```

---

## File Changes

| File | Action | Summary |
|------|--------|---------|
| `app/static/js/icrpg_catalog.js` | Modify | `statGrid()`, `collectStatGrid()`, `tierEditor()`, `collectTiers()`, `openTypeManage()`, `loadTypeManage()`, `renderTypeManage()`, delegated listeners |
| `app/templates/icrpg_catalog/index.html` | Modify | Description columns on HB Life Forms, Types, Loot tables; Manage button on Type rows; `#typeManageModal` HTML |
| `app/routes/icrpg_catalog.py` | Modify | 3 new routes: `manage_type`, `add_starting_loot`, `delete_starting_loot` |
| `docs/phase-19j-plan.md` | Create | This plan doc |

---

## New Backend Routes

```python
GET  /icrpg-catalog/types/<id>/manage
     → {type_name, abilities, starting_loot, all_loot, all_spells}

POST /icrpg-catalog/types/<id>/starting-loot/add
     body: {loot_def_id: X}  OR  {spell_id: Y}
     → {ok: True, id: <new sl id>}

POST /icrpg-catalog/types/<id>/starting-loot/<sl_id>/delete
     → {ok: True}
```

---

## Verification

- [ ] Create/edit a Life Form — stat grid appears; set STR+1 and CON-1, save → bonuses JSON stored correctly; on re-edit fields are pre-filled
- [ ] Create/edit Loot — effects grid appears; set DEFENSE+2 and EQUIPPED_SLOTS+1, save → effects JSON correct
- [ ] Create/edit a Milestone Path — tier accordion appears; add items to Tier 1 and Tier 3, save → tiers JSON stored correctly
- [ ] Import a builtin Type → gear button appears → click Manage → abilities list shows imported abilities with Edit/Delete
- [ ] In Manage modal: add a starting loot item → appears in list → Remove it → disappears

# Phase 19d: ICRPG Integration Completion

## Context
Phases 19a-c built the ICRPG catalog models, character sheet view with AJAX quick-edit, and the 8-step creation wizard. What's missing: (1) no UI to add loot/abilities to an existing character, (2) no way to create homebrew catalog items, (3) ICRPG characters don't appear correctly in the player wiki or combat tracker.

**Branch:** `feature/phase-19d-icrpg-integration`

## Features

| Feature | Status | Notes |
|---------|--------|-------|
| Add Loot modal on sheet | Planned | Catalog/Spell/Custom tabs, slot picker |
| Add Ability modal on sheet | Planned | Catalog/Custom tabs, kind picker |
| Custom loot endpoint update | Planned | Accept custom_name + custom_desc |
| ICRPG wiki PC detail | Planned | Read-only, player-safe sheet view |
| Combat tracker ICRPG stats | Planned | HP, Defense, stat totals for PCs |
| Homebrew catalog CRUD | Planned | Tabbed page for 7 entity types |
| ICRPG Catalog nav link | Planned | Conditional in Reference dropdown |

## Part 1: Add Loot / Add Ability UI on Sheet

- Pass `sheet_catalog` (loot defs, spells, abilities) as embedded JSON to sheet template
- Update `add-loot` endpoint to accept `custom_name` + `custom_desc` for one-off items
- Add Loot modal: 3 tabs (Catalog, Spell, Custom) + slot picker (equipped/carried)
- Add Ability modal: 2 tabs (Catalog, Custom) + kind picker
- JS handlers populate dropdowns from SHEET_CATALOG, POST via existing endpoints

## Part 2: Homebrew Catalog CRUD

- New Blueprint `icrpg_catalog_bp` at `/icrpg-catalog/`
- Single tabbed page: Worlds, Life Forms, Types, Abilities, Loot, Spells, Milestone Paths
- AJAX CRUD (POST JSON, return JSON) per entity type
- GM-only, campaign-scoped, ICRPG-only
- `is_icrpg` context processor flag + conditional nav link

## Part 3: Wiki + Combat Tracker Integration

- Wiki: detect ICRPG campaign, render `wiki/pcs/icrpg_detail.html` (read-only, no GM data)
- Combat: build ICRPG stats dict (HP, HP Max, Defense, stat totals) for PCs with sheets
- Combat template: use explicit `hp_current`/`hp_max` fields when available

## Implementation Order

1. Part 1: Add Loot/Ability modals
2. Part 3: Wiki + Combat integration
3. Part 2: Homebrew CRUD

# Phase 19: ICRPG Character Sheet Builder

## Overview
Full ICRPG character sheet system integrated with the existing PC entity. Includes a global ICRPG catalog (worlds, life forms, types, abilities, loot, spells, milestone paths) seeded from the Master Edition, homebrew CRUD for custom content, a character creation wizard, and mixed player/GM editing.

The ICRPG sheet only appears when `campaign.system` contains "ICRPG" (case-insensitive). Other systems keep the existing generic PC view.

## Architecture
- **Separate `ICRPGCharacterSheet` model** linked 1:1 to `PlayerCharacter` (not added columns to PC)
- Catalog models use `is_builtin` + `campaign_id` pattern for global vs. homebrew scope
- Spells ARE loot in ICRPG — no separate char spell model; `ICRPGCharLoot` handles both via `loot_def_id` or `spell_id`
- Computed properties on the sheet handle stat totals (base + race + loot, cap 10)

## New Models (11 tables)

### Catalog
| Model | Table | Purpose |
|-------|-------|---------|
| ICRPGWorld | icrpg_worlds | 5 official worlds + homebrew |
| ICRPGLifeForm | icrpg_life_forms | Races with JSON stat bonuses |
| ICRPGType | icrpg_types | Classes (Warrior, Mage, Pilot, etc.) |
| ICRPGAbility | icrpg_abilities | Starting/milestone/mastery abilities per type |
| ICRPGLootDef | icrpg_loot_defs | Reusable loot blueprints with JSON effects |
| ICRPGStartingLoot | icrpg_starting_loot | Links types to their starting loot picks |
| ICRPGSpell | icrpg_spells | Spell catalog with type/level/target/duration |
| ICRPGMilestonePath | icrpg_milestone_paths | 5 paths (Iron/Smoke/Amber/Oak/Hawk) with 4 tiers |

### Character Sheet
| Model | Table | Purpose |
|-------|-------|---------|
| ICRPGCharacterSheet | icrpg_character_sheets | 1:1 PC extension with stats/effort/HP/etc. |
| ICRPGCharLoot | icrpg_char_loot | Equipped/carried items on a character |
| ICRPGCharAbility | icrpg_char_abilities | Abilities on a character |

## Seed Data
All 5 worlds seeded from ICRPG Master Edition:
- **Alfheim** — 5 life forms, 6 types (Warrior, Hunter, Shadow, Bard, Mage, Priest)
- **Warp Shell** — 6 life forms, 6 types (Pilot, Gunner, Mechanic, Navigator, Scientist, Echo)
- **Ghost Mountain** — 3 life forms, 8 types (Tracker, Wraith, Brave, Gambler, Shaman, Mariachi, Gunslinger, Old Timer)
- **Vigilante City** — world only (uses Powers system, different structure)
- **Blood and Snow** — 1 life form (uses Alfheim types)
- **60+ spells**, **50+ basic loot items**, **5 milestone paths** with full tier rewards

Seed command: `FLASK_APP=run.py python3 -m flask seed-icrpg-catalog`

## Sub-Phases

| Sub-Phase | Focus | Status |
|-----------|-------|--------|
| **19a** | Models + migration + seed data + CLI command | In Progress |
| **19b** | Character sheet view template + AJAX quick-edit | Planned |
| **19c** | Character creation wizard (8-step multi-step form) | Planned |
| **19d** | Homebrew catalog CRUD + wiki/combat integration | Planned |

### Phase 19a: Models + Seed Data
- Branch: `feature/phase-19a-icrpg-catalog`
- All 11 ICRPG models in `app/models.py`
- Migration: `k1l2m3n4o5p6_add_icrpg_catalog_and_character_sheet.py`
- Seed JSON: `icrpg_worlds.json`, `icrpg_life_forms.json`, `icrpg_types.json`, `icrpg_milestone_paths.json`
- Existing seed data imported: `icrpg_spells.json`, `icrpg_starter_loot.json`
- CLI: `flask seed-icrpg-catalog`

### Phase 19b: Character Sheet View + Quick Edit
- ICRPG sheet template with stat grid, effort, loot, abilities
- Conditional routing: ICRPG campaigns get the sheet, others keep generic view
- AJAX quick-edit for HP, hero coin, dying timer, nat 20, equip/unequip

### Phase 19c: Character Creation Wizard
- 8-step wizard: World > Life Form > Type > Stats (6 pts) > Effort (4 pts) > Starting Ability > Starting Loot > Review & Name
- Creates both PlayerCharacter and ICRPGCharacterSheet in one transaction

### Phase 19d: Homebrew CRUD + Polish
- Catalog browser blueprint (`/icrpg-catalog`)
- Full CRUD for all catalog entity types (builtin read-only, homebrew editable)
- Wiki integration, combat tracker ICRPG stats

## Player Editing Permissions
- **Players can:** adjust HP, toggle hero coin, dying timer, nat 20 count, equip/unequip loot, edit name/story/description
- **GM only:** world/life form/type, base stats/effort, add/remove loot/abilities, hearts, coin, GM hooks/notes

# Phase 19i: Expand ICRPG Seed Data + Cross-World Loot

## Context
Three worlds (Ghost Mountain, Vigilante City, Blood and Snow) had zero basic starter loot seeded, so the wizard's "Choose Basic Loot" step auto-skipped for them. Ghost Mountain also had its own 25-spell list not in the catalog. Mage-specific loot (18 items) was also missing. Per ICRPG rules, Ghost Mountain characters can choose from Alfheim's basic loot pool too, requiring a cross-world sharing mechanism.

## Features

| Feature | Status | Notes |
|---------|--------|-------|
| Ghost Mountain basic loot (24 items) | Complete | 9 equipment + 15 weapons |
| Vigilante City basic loot (10 items) | Complete | |
| Blood and Snow starter loot (10 items) | Complete | |
| Mage Starting Loot (8 items) | Complete | Global (world_id=NULL), catalog-only |
| Mage Equipment (10 items) | Complete | Global (world_id=NULL), catalog-only |
| Ghost Mountain Holy Spells (12) | Complete | WIS casting stat |
| Ghost Mountain Infernal Spells (14) | Complete | INT casting stat (unique to GM) |
| Cross-world loot sharing | Complete | `include_world_loot` JSON column on ICRPGWorld |
| Homebrew catalog support | Complete | World form has "Include Loot From" field |

## Key Changes
- `include_world_loot` column on `ICRPGWorld` — stores world names whose basic loot also appears in the wizard pool (e.g., Ghost Mountain includes Alfheim)
- Seed function honors explicit `casting_stat` from spell JSON (needed because GM Infernal spells use INT, not the default WIS)
- Wizard serialization and validation expanded to include referenced worlds' basic loot
- 62 new loot items + 26 new spells seeded

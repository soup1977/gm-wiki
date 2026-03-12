# Phase 19l: ICRPG Homebrew AI Generator + Retheme

## Context

The ICRPG catalog is fully manual. This phase adds AI-assisted homebrew creation: an "AI Ideas" button on each entity section generates 3–5 thematically appropriate suggestions (with stat grids, effects, and tier data already filled in) that the GM can add to their catalog in one click. A "Retheme" button on existing entries lets the AI reskin an entry for a different setting (e.g., import a fantasy Dwarf, retheme it to Sci-Fi Space Miner).

Also adds a dynamic Anthropic model list to the Settings page — the dropdown fetches available models from the API rather than using a hardcoded list.

**Branch:** `feature/icrpg-ai-generator`

---

## Features

| Feature | Status | Notes |
|---------|--------|-------|
| Dynamic Anthropic model list in Settings | Planned | GET /api/ai/anthropic-models; fallback to hardcoded list |
| AI Ideas button per entity type (6 types) | Planned | Life Forms, Types, Abilities, Loot, Spells, Paths |
| Generate ICRPG homebrew suggestions | Planned | POST /api/ai/generate-icrpg → array of suggestions |
| Retheme button on each homebrew row | Planned | Reskins name/description/flavor, keeps mechanics |
| Retheme result: Save as New or Overwrite | Planned | Overwrite calls existing edit route |
| Results modal with Add to Catalog buttons | Planned | Green checkmark on success, button disabled |

---

## ICRPG Game System Context (in prompts)

All AI prompts include an ICRPG primer: d20 roll-under, effort dice (d4/d6/d8/d10/d12), Hearts = HP, Loot = equipment in slots, Types = character classes with abilities, Life Forms = race/species with stat bonuses. Balance guidance (not hard limits): stat bonuses typically +1–2 per trait, total effort bonus usually +1; be creative but don't give +6 to every stat.

---

## JSON Schemas per Entity Type

**lifeform:** `{ name, description, bonuses: {"STR": 1, "BASIC_EFFORT": 1} }`
**type:** `{ name, description }`
**ability:** `{ name, description, ability_kind: "starting|milestone|mastery" }`
**loot:** `{ name, description, loot_type: "Weapon|Armor|...", effects: {"WEAPON_EFFORT": 1}, slot_cost: 1, coin_cost: null }`
**spell:** `{ name, description, spell_type: "Arcane|Holy|Infernal", casting_stat: "INT|WIS", level: 1, target, duration }`
**path:** `{ name, description, tiers: {"1": [{"name":"...","description":"..."}], "2":[...], "3":[...], "4":[...]} }`

---

## New Backend Routes (`app/routes/ai.py`)

```
GET  /api/ai/anthropic-models
     → { models: [{id, display_name}, ...] }   (calls Anthropic /v1/models API)

POST /api/ai/generate-icrpg
     body: { entity_type, concept, count, world_id }
     → { suggestions: [ {...}, ... ] }

POST /api/ai/retheme-icrpg
     body: { entity_type, existing_data, theme, world_id }
     → { suggestion: {...} }
```

Both generation routes use `get_feature_provider('generate')` and `_extract_json()` from the existing pattern. Campaign context injected via `_get_active_world_context()`.

---

## File Changes

| File | Action | Summary |
|------|--------|---------|
| `app/routes/ai.py` | Modify | 3 new routes: anthropic-models, generate-icrpg, retheme-icrpg |
| `app/templates/settings/index.html` | Modify | JS fetches model list dynamically on Anthropic section reveal |
| `app/templates/icrpg_catalog/index.html` | Modify | AI Ideas + Retheme buttons per section/row; `#icrpgAIModal` HTML |
| `app/static/js/icrpg_catalog.js` | Modify | openIcrpgAI, openIcrpgRetheme, runIcrpgGenerate, runIcrpgRetheme, renderSuggestions, addIcrpgSuggestion |
| `docs/phase-19l-plan.md` | Create | This plan doc |

No model changes. No migration.

---

## Verification

- [ ] Settings page: Anthropic section shows dynamic model list from API (or fallback to hardcoded 3)
- [ ] Click "AI Ideas" on Life Forms → modal opens → enter "aquatic humanoid" → 3 suggestions with names, descriptions, bonus grids
- [ ] Click "Add to Catalog" → appears in Homebrew Life Forms table → edit it → stat grid pre-fills correctly
- [ ] Click "AI Ideas" on Loot with "fire weapons" → suggestions include effects JSON → stores correctly
- [ ] Click "AI Ideas" on Paths → suggestions include 4 tiers → tier accordion shows correctly on edit
- [ ] Click Retheme on a Life Form → enter "sci-fi space opera" → reskinned suggestion appears → "Save as New" creates second entry → "Overwrite" replaces original

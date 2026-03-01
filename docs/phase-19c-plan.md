# Phase 19c: ICRPG Character Creation Wizard

## Overview
8-step character creation wizard that creates both a PlayerCharacter and an ICRPGCharacterSheet (with starting loot + abilities) in a single transaction. Follows the genesis wizard pattern — single-page template with client-side step navigation and embedded catalog data.

## The 8 Steps

| Step | Title | UI | Validation |
|------|-------|-----|-----------|
| 1 | **Choose World** | Radio cards (name + description) | worldId set |
| 2 | **Choose Life Form** | Radio cards filtered by world. Show bonus summary | lifeFormId set |
| 3 | **Choose Type** | Radio cards filtered by world. Preview abilities + loot | typeId set |
| 4 | **Allocate Stats** | 6 rows with +/- buttons, life form bonuses shown, "Points remaining: X/6" | total = 6 |
| 5 | **Allocate Effort** | 5 rows (Basic d4 / Weapons d6 / Guns d8 / Magic d10 / Ultimate d12) with +/- | total = 4 |
| 6 | **Starting Ability** | Radio buttons for type's starting abilities | 1 selected |
| 7 | **Starting Loot** | Radio buttons for type's starting loot options | 1 selected |
| 8 | **Review & Create** | Name/player/story inputs + full summary | name + player filled |

## File Changes

| File | Action | Summary |
|------|--------|---------|
| `app/routes/pcs.py` | Modify | Add GET wizard route, POST create route, `_serialize_catalog` helper |
| `app/templates/pcs/icrpg_wizard.html` | Create | 8-step wizard template |
| `app/static/js/icrpg_wizard.js` | Create | Client-side wizard logic |
| `app/static/css/custom.css` | Modify | Add ~10 lines for wizard card selection styles |
| `app/templates/pcs/list.html` | Modify | Add "ICRPG Wizard" button for ICRPG campaigns |

**No changes to:** `app/models.py`, `app/__init__.py`, `migrations/`

## Architecture

### Data Strategy
All catalog data embedded in template as JSON (`CATALOG` object). No AJAX per step — client-side filtering only. Data is small (~5 worlds, ~15 life forms, ~20 types).

### Routes
- **GET `/pcs/icrpg/wizard`** — Verify ICRPG campaign, query catalog, serialize, render template
- **POST `/pcs/icrpg/create`** — Accept JSON, validate all fields server-side, create PC + sheet + loot + abilities in one transaction

### JavaScript
- State object tracks all wizard selections
- `showStep(n)` toggles visibility and progress bar
- Per-step render functions filter CATALOG and build dynamic UI
- Cascade resets: changing world resets downstream selections
- Submit POSTs JSON to create endpoint, redirects on success

### Validation
- **Client-side:** Required selections, point totals, required name fields
- **Server-side:** All FK relationships verified, stat/effort totals checked, ability/loot ownership validated

## Edge Cases
- World with no life forms/types: show message, disable Next
- Life form with non-numeric bonuses (ABILITY text): display as info text
- Life form with HEARTS bonus: adjust hearts_max and hp_current on creation
- Non-ICRPG campaign: GET route redirects with flash error

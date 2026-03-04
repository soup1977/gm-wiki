# Copy Entity to Another Campaign — Implementation Plan

## Context
Currently there's no way to reuse entities across campaigns. If Craig creates a great NPC, location, or random table in one campaign, the only way to get it into another campaign is to manually recreate it. This feature adds a "Copy to Campaign" button on entity detail pages that duplicates the entity into a selected target campaign.

## Scope
- **Supported types**: NPC, Location, Quest, Item, Faction, CompendiumEntry, AdventureSite (Story Arc), RandomTable, Encounter
- **Excluded**: PlayerCharacter (too complex with ICRPG sheets, stat templates, session attendance)
- **FK handling**: Cross-campaign references (home_location, faction, story_arc, etc.) are nulled out
- **Tags**: Recreated in target campaign via `get_or_create_tags()`
- **Images**: Duplicated with new UUID filenames
- **Shortcodes**: Left as-is (will show as broken links but remain readable)
- **Child rows**: TableRow and EncounterMonster rows are cloned with the parent

## Files to Create

### 1. `app/routes/copy_entity.py` — New Blueprint
Single POST route: `/copy-entity/<entity_type>/<int:entity_id>`

Dispatch table maps type strings to copier functions:
- `npc` → `_copy_npc` (null: home_location_id, faction_id, story_arc_id; clear: connected_locations; dup: portrait)
- `location` → `_copy_location` (null: parent_location_id, faction_id, story_arc_id; clear: connected_locations; dup: map)
- `quest` → `_copy_quest` (null: faction_id, story_arc_id; clear: involved_npcs, involved_locations)
- `item` → `_copy_item` (null: owner_npc_id, origin_location_id, story_arc_id; dup: image)
- `faction` → `_copy_faction` (no FKs to null)
- `compendium` → `_copy_compendium` (no FKs to null)
- `adventure_site` → `_copy_adventure_site` (clear: sessions; copy milestones JSON)
- `random_table` → `_copy_random_table` (clone TableRow children; set is_builtin=False)
- `encounter` → `_copy_encounter` (null: session_id, loot_table_id, story_arc_id; clone EncounterMonster children; reset status to 'planned')

Helpers:
- `_duplicate_image(filename)` — copies file in UPLOAD_FOLDER with UUID name
- `_copy_tags(source, target_campaign_id)` — recreates tags via `get_or_create_tags()`

Post-copy: switch `session['active_campaign_id']` to target campaign, redirect to new entity detail page, flash success message.

### 2. `app/templates/partials/_copy_entity_modal.html` — Shared modal
Bootstrap modal with campaign dropdown (filters out current campaign). Receives `copy_entity_type` and `copy_entity_id` via `{% set %}` before `{% include %}`.

Only renders when `user_campaigns|length > 1`.

## Files to Modify

### 3. `app/__init__.py`
- Register `copy_entity_bp` Blueprint
- Extend existing `inject_active_campaign` context processor (line 302) to also return `user_campaigns` list

### 4-12. Nine detail templates (add copy button + include modal)
Each gets:
- A "Copy" button (`btn btn-sm btn-outline-info`) in the action buttons area, only shown when `user_campaigns|length > 1`
- `{% include 'partials/_copy_entity_modal.html' %}` at bottom of content block with appropriate `{% set %}` vars

Templates:
- `app/templates/npcs/detail.html`
- `app/templates/locations/detail.html`
- `app/templates/quests/detail.html`
- `app/templates/items/detail.html`
- `app/templates/factions/detail.html`
- `app/templates/compendium/detail.html`
- `app/templates/adventure_sites/detail.html`
- `app/templates/tables/detail.html` (non-builtin tables only)
- `app/templates/encounters/detail.html`

## Implementation Order
1. Extend context processor to inject `user_campaigns`
2. Create modal partial template
3. Write `copy_entity.py` with route + all copier functions
4. Register Blueprint in `__init__.py`
5. Add button + include to all 9 detail templates
6. Test each entity type

## Key Existing Code to Reuse
- `get_or_create_tags()` in `app/models.py` (line 612) — tag recreation
- `inject_active_campaign()` in `app/__init__.py` (line 302) — extend with user_campaigns
- `UPLOAD_FOLDER` from `config.py` (line 25) — image path
- `ActivityLog.log_event()` — audit trail
- Delete modal pattern in detail templates — same structure for copy modal

## Verification
1. Create a second test campaign
2. Copy each of the 9 entity types and verify:
   - Entity appears in target campaign with " (copy)" suffix
   - Cross-campaign FKs are null
   - Tags exist in target campaign
   - Images are duplicated (separate files)
   - TableRow / EncounterMonster children are cloned
   - Active campaign switches to target after copy
   - ActivityLog shows the copy event
3. Verify button doesn't appear when user has only 1 campaign
4. Verify user can't copy to a campaign they don't own

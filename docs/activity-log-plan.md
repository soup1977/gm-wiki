# Activity Log / Event Viewer

## Context

Craig wants to track "who changed what and when" across the app. This is useful for debugging unexpected data changes on the Unraid server, reviewing what happened during a session, and having an audit trail. The feature was planned in `docs/future-ideas.md` and chosen as the next priority.

**Branch:** `feature/activity-log`

---

## Model

Add `ActivityLog` to `app/models.py` (after `AppSetting`, ~line 713):

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `user_id` | FK → users.id | nullable (system actions) |
| `campaign_id` | FK → campaigns.id | nullable (global entities like bestiary) |
| `action` | String(50) | `created`, `edited`, `deleted`, `status_changed`, `error` |
| `entity_type` | String(50) | `npc`, `location`, `quest`, `item`, `session`, etc. |
| `entity_id` | Integer | nullable (still stored for deleted entities) |
| `entity_name` | String(200) | snapshot at log time |
| `details` | String(200) | optional context, e.g. "status: alive → dead" |
| `timestamp` | DateTime | indexed, default `utcnow` |

Includes a `log_event()` static method (fire-and-forget — wraps everything in try/except so a log failure never breaks a save). The log entry is added to the same transaction as the entity save, so if the save rolls back, the log entry does too.

---

## Migration

**File:** `migrations/versions/o5p6q7r8s9t0_add_activity_log.py`
- Chains from `n4o5p6q7r8s9`
- Creates `activity_log` table with indexes on `timestamp` and `campaign_id`

---

## Admin Viewer

**Route:** Add to `app/routes/admin.py` — `GET /admin/activity-log`

- Filter dropdowns: Campaign, Entity Type, User, Action
- Paginated (50 per page)
- Table columns: Timestamp, User, Campaign, Action, Entity Type, Entity Name, Details
- Action badges color-coded (created=green, edited=info, deleted=danger, status_changed=warning, error=dark-red)
- Entity name links to detail page when entity still exists (use an `ENTITY_URL_MAP` dict passed to template)
- "Purge Old Entries" button at top-right

**Template:** `app/templates/admin/activity_log.html` — follows pattern of `admin/users.html`

**Nav link:** Add to `app/templates/base.html` in the admin dropdown (line ~182, after User Management)

---

## log_event() Calls — 17 Route Files, ~55 Call Sites

Core entity routes (3-4 calls each: create, edit, delete, optional status_change):

| Route File | Functions |
|------------|-----------|
| `app/routes/npcs.py` | `create_npc`, `edit_npc`, `set_npc_status`, `delete_npc` |
| `app/routes/locations.py` | `create_location`, `edit_location`, `delete_location` |
| `app/routes/quests.py` | `create_quest`, `edit_quest`, `set_quest_status`, `delete_quest` |
| `app/routes/items.py` | `create_item`, `edit_item`, `delete_item` |
| `app/routes/sessions.py` | `create_session`, `edit_session`, `delete_session` |
| `app/routes/compendium.py` | `create_entry`, `edit_entry`, `delete_entry` |
| `app/routes/factions.py` | `create_faction`, `edit_faction`, `delete_faction` |
| `app/routes/encounters.py` | `create_encounter`, `edit_encounter`, `delete_encounter` |
| `app/routes/pcs.py` | `create_pc`, `edit_pc`, `delete_pc`, `icrpg_create_character` |
| `app/routes/adventure_sites.py` | `create_site`, `genesis_save`, `edit_site`, `delete_site` |
| `app/routes/campaigns.py` | `create_campaign`, `edit_campaign`, `delete_campaign` |
| `app/routes/bestiary.py` | `create_entry`, `edit_entry`, `delete_entry`, `spawn_instance` |
| `app/routes/monsters.py` | `edit_instance`, `delete_instance`, `promote_to_npc` |
| `app/routes/tables.py` | `create_table`, `edit_table`, `delete_table` |
| `app/routes/quick_create.py` | `quick_create` (new entity only) |
| `app/routes/ai.py` | `genesis_create_entity`, `save_idea_as_encounter` |
| `app/routes/session_mode.py` | `save_post_session` |
| `app/routes/admin.py` | `create_user`, `delete_user` |

**Excluded** (too noisy / no DB writes): ICRPG sheet AJAX endpoints (hp, coin, loot, etc.), toggle_visibility, seed/import operations.

---

## Error Logging

Errors use `action='error'` with `entity_type` describing the subsystem and `details` capturing the error message.

Since errors happen outside normal DB transactions, `log_event()` needs to handle these with its own commit. Add an optional `immediate=True` param that does `db.session.add(entry); db.session.commit()` in its own mini-transaction (still wrapped in try/except so it's fire-and-forget).

### AI Failures (`app/routes/ai.py`)

Log in every `except AIProviderError` and `except json.JSONDecodeError` block across all endpoints:

| Endpoint | entity_type | details |
|----------|-------------|---------|
| `smart_fill` (~line 358) | `ai_smart_fill` | error message |
| `generate_entry` (~line 575) | `ai_generate` | error message |
| `brainstorm_arcs` (~line 633) | `ai_brainstorm` | error message |
| `site_ideas` (~line 721) | `ai_site_ideas` | error message |
| `session_prep` (~line 805) | `ai_session_prep` | error message |
| `draft_summary` (~line 887) | `ai_draft_summary` | error message |
| `generate_arc_structure` (~line 950) | `ai_arc_structure` | error message |
| `propose_arc_entities` (~line 1012) | `ai_propose_entities` | error message |
| `genesis_create_entity` (~line 1090) | `ai_genesis` | error message |

### Failed Logins (`app/routes/auth.py`)

Log at line ~32 where `flash('Invalid username or password.')` is called.

### SD Image Generation Failures (`app/routes/sd_generate.py`)

Log in the `except SDProviderError` block.

### Import Failures

| File | Where | entity_type | details |
|------|-------|-------------|---------|
| `app/routes/obsidian_import.py` (~line 260) | DB commit failure | `obsidian_import` | error message |
| `app/routes/bestiary_import.py` (~line 249, 273, 309) | Open5e API failure | `bestiary_import` | "API unreachable" |
| `app/routes/srd_import.py` (~line 82) | D&D 5e API failure | `srd_import` | "API unreachable" |

### Campaign Assistant Errors (`app/routes/campaign_assistant.py`)

| Where | entity_type | details |
|-------|-------------|---------|
| `send_message` (~line 200) AI failure | `campaign_assistant` | error message |
| `save_entity` (~line 304) DB failure | `campaign_assistant` | "Entity save failed: ..." |

---

## Cleanup / Purge

- **AppSetting keys:** `activity_log_retention_days` (default 90), `activity_log_max_rows` (default 10000)
- **CLI command:** `flask purge-activity-log` — deletes entries older than retention period
- **Auto-purge:** Probabilistic `after_request` hook (~1% of requests) trims rows beyond max
- **Campaign delete:** Clean up log entries for deleted campaigns in `delete_campaign()`
- **Settings UI:** Two number inputs added to `app/templates/settings/index.html` and saved in `app/routes/settings.py`

---

## Files Changed

| File | Action | Summary |
|------|--------|---------|
| `app/models.py` | Modify | Add `ActivityLog` model + `log_event()` static method |
| `migrations/versions/o5p6q7r8s9t0_*.py` | Create | New table migration |
| `app/routes/admin.py` | Modify | Add activity log viewer route + purge route |
| `app/templates/admin/activity_log.html` | Create | Admin viewer template |
| `app/templates/base.html` | Modify | Add nav link in admin dropdown (~line 182) |
| `app/__init__.py` | Modify | Add `purge-activity-log` CLI command + `after_request` auto-purge |
| `app/routes/settings.py` | Modify | Save retention/max-rows settings |
| `app/templates/settings/index.html` | Modify | Add retention/max-rows fields |
| 17 route files | Modify | Add `log_event()` calls after commits |
| `app/routes/ai.py` | Modify | Add error logging in 9 except blocks |
| `app/routes/auth.py` | Modify | Log failed login attempts |
| `app/routes/sd_generate.py` | Modify | Log SD generation failures |
| `app/routes/obsidian_import.py` | Modify | Log import DB commit failures |
| `app/routes/bestiary_import.py` | Modify | Log Open5e API failures |
| `app/routes/srd_import.py` | Modify | Log D&D 5e API failures |
| `app/routes/campaign_assistant.py` | Modify | Log AI + save failures |

---

## Implementation Order

1. **Model + migration** — `ActivityLog` class, `log_event()`, migration file, run upgrade
2. **Admin viewer** — route, template, nav link. Verify empty table renders.
3. **Core entity routes** — Add `log_event()` to the 10 main entity CRUD files (npcs, locations, quests, items, sessions, compendium, factions, encounters, pcs, adventure_sites). Test by creating/editing/deleting a few things.
4. **Supporting routes** — campaigns, bestiary, monsters, tables, quick_create, ai (CRUD calls), session_mode, admin
5. **Error logging** — AI failures (9 endpoints in ai.py), failed logins (auth.py), SD failures (sd_generate.py), import failures (obsidian/bestiary/srd), campaign assistant errors
6. **Cleanup + settings** — CLI command, auto-purge, settings UI, campaign delete cleanup
7. **Polish** — review badge colors, verify pagination, test on tablet viewport, add `error` badge color (red/dark)

---

## Verification

1. Run migration: `FLASK_APP=run.py python3 -m flask db upgrade`
2. Create an NPC → check `/admin/activity-log` shows "created npc" entry
3. Edit and delete entities → verify entries appear with correct action/type
4. Filter by campaign, entity type, action → verify filter works
5. Click entity name → navigates to detail page
6. Trigger an AI call with bad/missing API key → verify "error" entry logged with details
7. Attempt login with wrong password → verify "error auth" entry logged
8. Filter by `action=error` → shows only error entries
9. Change retention to 0 days, run `flask purge-activity-log` → entries cleared
10. Verify no errors when logging fails (e.g., temporarily break the model, ensure saves still work)

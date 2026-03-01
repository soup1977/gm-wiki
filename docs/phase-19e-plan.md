# Phase 19e: Player Sheet Permissions

## Context
Phase 19d added Add Loot/Ability modals and the Homebrew Catalog, but all add/remove actions are GM-only. Players who claimed their character can only adjust HP, toggle hero coin, equip/unequip loot, and record Nat 20s. This phase expands player capabilities and adds a per-PC toggle for stat editing.

**Branch:** `feature/phase-19e-player-sheet-permissions`

---

## Features

| Feature | Status | Notes |
|---------|--------|-------|
| Players can add loot to own sheet | Planned | Change template guards from `is_admin` to `can_edit` |
| Players can remove loot from own sheet | Planned | Same guard swap + remove server-side admin check |
| Players can add abilities to own sheet | Planned | Same pattern |
| Players can remove abilities from own sheet | Planned | Same pattern |
| Per-PC stat edit toggle | Planned | New `allow_player_edit` field on ICRPGCharacterSheet |
| GM toggle UI | Planned | Switch in Status card, GM-only visible |
| Loot bonus verification | Planned | Verify `_loot_bonus()` handles custom/spell items safely |
| Future roles documentation | Planned | Document Player/Asst GM/GM/Admin permission matrix |

---

## File Changes

| File | Action | Summary |
|------|--------|---------|
| `app/models.py` | Modify | Add `allow_player_edit` boolean to `ICRPGCharacterSheet` |
| `app/routes/pcs.py` | Modify | Expand catalog access, remove admin guards from 4 endpoints, add toggle endpoint, update stat/effort permission |
| `app/templates/pcs/icrpg_sheet.html` | Modify | Swap 11 `is_admin` guards to `can_edit`/`can_edit_stats`, add GM toggle switch |
| `app/static/js/icrpg_sheet.js` | Modify | Add toggle-player-edit handler |
| `migrations/versions/l2m3n4o5p6q7_*.py` | Create | Migration for `allow_player_edit` column |
| `docs/future-roles-permissions.md` | Create | Document future permission system |

**One new migration. No new templates or blueprints.**

---

## Key Design Decisions

1. **Reuse `_can_edit()` for loot/ability permissions** — this function already checks admin OR owner OR unclaimed. The explicit `is_admin` guards on add/remove endpoints were redundant since `_get_sheet_or_error()` already enforces `_can_edit()`.

2. **Per-PC toggle (not campaign-level)** — `allow_player_edit` is on `ICRPGCharacterSheet`, so the GM can enable stat editing for individual characters. Default is False (opt-in).

3. **`can_edit_stats` template variable** — new context var that is True when admin OR (toggle is on AND user owns the PC). Stat/effort +/- buttons use this instead of `is_admin`.

4. **No wiki changes** — the wiki remains read-only for now. A future roles/permissions system (documented in `docs/future-roles-permissions.md`) will replace the wiki with proper view/edit role gating.

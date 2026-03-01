# Phase 19b: ICRPG Character Sheet View + Quick Edit

## Context
Phase 19a is complete — 11 ICRPG database models exist and are populated with seed data (5 worlds, 15 life forms, 20 types, 205 abilities, 97 loot defs, 153 spells, 5 milestone paths). Now we need the **character sheet view** — when a PC belongs to an ICRPG campaign, their detail page shows a full ICRPG sheet instead of the generic PC detail, plus AJAX quick-edit endpoints for live play.

**Branch:** `feature/phase-19b-icrpg-sheet`

---

## File-by-File Changes

| File | Action | Summary |
|------|--------|---------|
| `app/routes/pcs.py` | Modify | Add ICRPG conditional routing in `pc_detail`, `_get_sheet_or_error` helper, 6 AJAX endpoints, "create blank sheet" endpoint |
| `app/templates/pcs/icrpg_sheet.html` | Create | Full ICRPG character sheet template (~200 lines) |
| `app/templates/pcs/detail.html` | Modify | Add ICRPG banner for PCs without a sheet (~8 lines) |
| `app/static/js/icrpg_sheet.js` | Create | AJAX handlers for HP, hero coin, dying, nat20, equip/unequip (~120 lines) |
| `app/static/css/custom.css` | Modify | Add ~15 lines of `icrpg-` prefixed styles |

**No changes to:** `app/__init__.py`, `app/models.py`, `migrations/`, `base.html`

---

## 1. Conditional Routing in `pc_detail` (pcs.py)

After loading the PC and building `stats_display`, check whether the campaign is ICRPG:

```python
campaign = Campaign.query.get(campaign_id)
is_icrpg = 'icrpg' in (campaign.system or '').lower()

if is_icrpg:
    sheet = pc.icrpg_sheet  # 1:1 backref, may be None
    if sheet:
        return render_template('pcs/icrpg_sheet.html',
                               pc=pc, sheet=sheet,
                               can_edit=_can_edit(pc),
                               is_owner=_is_owner(pc))
    else:
        # Show generic detail with "Create ICRPG Sheet" banner
        return render_template('pcs/detail.html', pc=pc,
                               stats_display=stats_display,
                               can_edit=_can_edit(pc),
                               show_icrpg_banner=True)
```

New imports: `Campaign`, `ICRPGCharacterSheet`, `ICRPGCharLoot` from models; `jsonify` from flask.

---

## 2. ICRPG Sheet Template Layout

Two-column responsive layout (`col-lg-4` / `col-lg-8`), stacks on tablets:

**LEFT COLUMN:**
- Portrait image
- World / Life Form / Type labels
- Story (one-liner concept)
- **Core Stats card** — table with columns: Stat | Base | +Race | +Loot | = Total (6 rows)
- **Effort card** — table with: Effort (die) | Base | +Bonuses | = Total (5 rows)
- **Status card:**
  - HP progress bar (green >50%, yellow 25-50%, red <25%) with +/- buttons
  - Hearts display
  - Defense value
  - Hero Coin toggle button (gold when active)
  - Dying Timer: 3 pips (filled = dying count) with +/- buttons
  - Coin count

**RIGHT COLUMN:**
- **Equipped Loot card** — list with unequip buttons, slot counter (X/10)
- **Carried Loot card** — list with equip buttons, slot counter (X/10)
- **Abilities card** — grouped by kind (starting, milestone, mastery)
- **Mastery Progress** — nat 20 count/20, mastery count/3, +1 nat20 button
- Description, Backstory, GM Hooks (warning border, GM-only), Notes, Sessions Attended

Data attributes div for JS: `<div id="icrpg-data" data-pc-id="{{ pc.id }}" data-can-edit="{{ 'true' if can_edit else 'false' }}">`

Loads `icrpg_sheet.js` in `{% block scripts %}`.

---

## 3. AJAX Quick-Edit Endpoints (all in pcs.py)

**Shared helper:**
```python
def _get_sheet_or_error(pc_id):
    pc = PlayerCharacter.query.get_or_404(pc_id)
    if pc.campaign_id != get_active_campaign_id():
        return None, (jsonify({'error': 'Not found.'}), 404)
    if not _can_edit(pc):
        return None, (jsonify({'error': 'Permission denied.'}), 403)
    sheet = pc.icrpg_sheet
    if not sheet:
        return None, (jsonify({'error': 'No ICRPG sheet.'}), 404)
    return sheet, None
```

| Endpoint | Method | Body | Returns | Notes |
|----------|--------|------|---------|-------|
| `/pcs/<id>/icrpg/hp` | POST | `{delta: +1/-1}` | `{hp_current, hp_max}` | Clamp 0..hp_max |
| `/pcs/<id>/icrpg/hero-coin` | POST | `{}` | `{hero_coin}` | Toggle boolean |
| `/pcs/<id>/icrpg/dying` | POST | `{delta: +1/-1}` | `{dying_timer}` | Clamp 0..3 |
| `/pcs/<id>/icrpg/nat20` | POST | `{}` | `{nat20_count, mastery_count}` | Auto-award mastery at 20, reset to 0 |
| `/pcs/<id>/icrpg/equip` | POST | `{loot_id, slot}` | `{slot, loot_id, equipped_slots, carried_slots, defense, stats, efforts}` | Validate slot capacity (10 max) |
| `/pcs/<id>/icrpg/create-sheet` | POST | `{}` | Redirect to pc_detail | GM-only, creates blank sheet |

**CSRF handling:** Use `X-CSRFToken` header from `<meta name="csrf-token">` tag (already in base.html). Same pattern as session_mode. Do NOT exempt `pcs_bp` — it has form-based routes that need CSRF.

---

## 4. JavaScript (`icrpg_sheet.js`)

IIFE pattern. On DOMContentLoaded:
- Read `pcId` and `canEdit` from `#icrpg-data` data attributes
- Read CSRF token from `meta[name="csrf-token"]`
- If !canEdit, return (no interactive elements)

`postAction(action, body, callback)` helper sends fetch POST with JSON + CSRF header.

**HP buttons:** Update `#icrpg-hp-current` text, progress bar width + color class.
**Hero Coin:** Toggle button between `btn-warning` (active) and `btn-outline-secondary`.
**Dying:** Update 3 pip icons (filled=danger, empty=secondary).
**Nat 20:** Update count text, also mastery count if auto-awarded.
**Equip/Unequip:** `window.location.reload()` — simplest approach since equipping changes stat totals, effort totals, defense, and both slot counters.

---

## 5. CSS Additions (~15 lines)

Minimal, prefixed with `icrpg-`:
- `.icrpg-stat-table td` — vertical-align: middle
- `.icrpg-stat-table .stat-total` — bold, slightly larger
- `.icrpg-stat-table .stat-bonus` — muted, smaller
- `.icrpg-hp-bar-wrap .progress` — height 1.5rem, transition on bar width
- `.icrpg-hero-coin i` — gold color when active
- `.icrpg-dying-pips i` — 1.2rem size
- `.icrpg-loot-item` — subtle bottom border, description muted/smaller

---

## 6. Edge Cases

- **No ICRPG sheet yet:** Generic detail with info banner + "Create ICRPG Sheet" button (POST to create-sheet endpoint, GM-only)
- **Equip over 10 slots:** Endpoint returns error, JS shows alert
- **Life form non-stat bonuses:** (e.g. `{"ABILITY": "Claw weapons"}`) — template filters to only show numeric bonuses in stat table; ability bonuses shown separately as text
- **Tablet usability:** `col-lg-4` / `col-lg-8` stacks below 992px; buttons sized for touch
- **Dying at 3:** Visual indicator (all pips red), but no auto-death — GM decides

---

## 7. Implementation Order

1. Modify `pcs.py` — conditional routing + helper + all 6 endpoints
2. Create `icrpg_sheet.html` — full template
3. Modify `detail.html` — add ICRPG banner
4. Create `icrpg_sheet.js` — wire up quick-edit buttons
5. Add CSS to `custom.css`
6. Test full flow manually

---

## 8. Verification

1. Start app with `python3 run.py`
2. Create/use an ICRPG campaign (system field contains "ICRPG")
3. Navigate to a PC — should see generic detail with "Create ICRPG Sheet" banner
4. Click "Create ICRPG Sheet" — should create blank sheet and redirect
5. Verify ICRPG sheet renders: stats, effort, HP bar, loot, abilities
6. Test quick-edit: HP +/-, hero coin toggle, dying +/-, nat 20 +1, equip/unequip
7. Verify permission: claiming player can quick-edit; non-owner cannot see buttons
8. Test non-ICRPG campaign — should still show generic PC detail

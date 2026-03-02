# Phase 19g: Active Effects Display

## Context
Phase 19f added structured `effects` JSON and color-coded badges for numeric bonuses (defense, stats, effort). However, many loot items and abilities have important GM-adjudicated text effects that aren't captured by the numeric system — things like "DEX rolls always HARD", "immune to fire", or "sacrifice the shield to absorb all damage". Players and GMs need a quick-reference view of all active text effects from equipped items and abilities.

**Branch:** `feature/phase-19g-active-effects`

---

## Features

| Feature | Status | Notes |
|---------|--------|-------|
| Active Effects card on ICRPG sheet | Complete | Collapsible card listing all equipped loot + ability descriptions |

---

## File Changes

| File | Action | Summary |
|------|--------|---------|
| `app/templates/pcs/icrpg_sheet.html` | Modify | Add collapsible Active Effects card between equipped loot and carried loot |
| `docs/phase-19g-plan.md` | Create | Phase plan doc |

**No model changes. No new migration. No JS changes.**

---

## Design Decisions

1. **Show full descriptions** rather than trying to regex-parse "important" phrases. The numeric bonuses are already shown as badges above — the Active Effects card serves as the "everything else" text reminder.

2. **Include abilities** alongside loot — abilities like "Walk on any surface" are just as important as loot effects at the table.

3. **Collapsible card** — the card starts expanded (`collapse show`) but can be collapsed to reduce visual noise. Uses Bootstrap collapse with a chevron indicator.

4. **Source badges** — ability entries get a small "ability" badge to distinguish them from loot effects.

5. **Only shows when there's data** — card is hidden entirely when no equipped items or abilities have descriptions.

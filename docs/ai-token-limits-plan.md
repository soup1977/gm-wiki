# AI Token Limits — Implementation Plan

## Context

Token limits are currently hardcoded across `app/routes/ai.py` and `app/routes/campaign_assistant.py`. A power user with a fast/expensive model may want higher limits; a budget user may want lower caps. This feature adds configurable per-feature token limits to the Settings page.

**Branch:** `feature/ai-token-limits`

---

## Current Hardcoded Values

| Call Site | File | Line | Current Value |
|-----------|------|------|---------------|
| Smart Fill | ai.py | 355 | 1024 |
| Generate Entry (standard) | ai.py | 576 | 2048 |
| Generate Entry (adventure_site) | ai.py | 538 | 8000 |
| Generate Entry (bestiary) | ai.py | 541 | 4096 |
| Improv Encounter | ai.py | 638 | 2048 |
| Hazard Flavor | ai.py | 732 | 2048 |
| Suggest Consequences | ai.py | 820 | 2048 |
| Suggest Milestones | ai.py | 906 | 2048 |
| Session Prep | ai.py | 973 | 2048 |
| Encounter Builder | ai.py | 1039 | 3000 |
| Genesis Wizard | ai.py | 1121 | 4096 (npc/location) / 2048 (others) |
| Campaign Assistant chat | campaign_assistant.py | 197 | 4096 |

---

## Design

### Three Grouped Settings

Rather than 12 individual settings, group them into 3 categories:

1. **Standard AI Tasks** (`ai_max_tokens_standard`, default: 2048)
   - Applies to: Smart Fill, Improv Encounter, Hazard Flavor, Suggest Consequences, Suggest Milestones, Session Prep, Encounter Builder
   - Smart Fill uses a 0.5x multiplier (1024 default)
   - Encounter Builder uses a 1.5x multiplier (3000 default)

2. **Generate Entry** (`ai_max_tokens_generate`, default: 2048)
   - Applies to: Generate Entry, Genesis Wizard (standard entity types)
   - Adventure Site uses a 4x multiplier (8000 default)
   - Bestiary uses a 2x multiplier (4096 default)

3. **Campaign Assistant** (`ai_max_tokens_assistant`, default: 4096)
   - Applies to: Campaign Assistant chat

### Helper Function

Add to `app/routes/ai.py`:

```python
def _get_max_tokens(setting_key, default, multiplier=1.0):
    """Read a token limit from AppSetting, apply multiplier, clamp to range."""
    from app.models import AppSetting
    base = int(AppSetting.get(setting_key, str(default)))
    value = int(base * multiplier)
    return max(256, min(value, 16384))
```

---

## Files to Modify

| File | Change |
|------|--------|
| `app/routes/ai.py` | Add `_get_max_tokens()` helper; replace 10 hardcoded values with calls |
| `app/routes/campaign_assistant.py` | Replace 1 hardcoded value with `_get_max_tokens()` call |
| `app/routes/settings.py` | Save/load 3 new AppSetting keys |
| `app/templates/settings/index.html` | Add "AI Token Limits" card with 3 number inputs |

**No migration needed** — uses existing `AppSetting` key/value store.

---

## Settings UI

Add a card to the Settings page (AI section) with:
- **Standard AI Tasks** — number input, min 256, max 8192, step 256, default 2048
- **Generate Entry** — number input, min 256, max 8192, step 256, default 2048
- **Campaign Assistant** — number input, min 256, max 8192, step 256, default 4096
- Help text explaining: "Smart Fill uses half this value. Adventure Site generation uses 4x. Bestiary uses 2x."

---

## Verification

1. Set Standard to 1024 → Smart Fill should use 512, Improv Encounter should use 1024
2. Set Generate to 4096 → Adventure Site should use 16384 (clamped), Bestiary should use 8192
3. Set Assistant to 2048 → Campaign Assistant chat should use 2048
4. Leave all blank → falls back to hardcoded defaults (no change in behavior)
5. App starts correctly with no settings saved (first run)

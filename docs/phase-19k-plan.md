# Phase 19k: Anthropic Model Selector in Settings

## Context

The AI provider hardcoded `model='claude-haiku-4-5-20251001'` in `_call_anthropic()`. The Settings page allowed configuring the API key but not the model. Craig wanted a dropdown to choose between available Anthropic models, persisted and used for all AI calls.

No database migration needed — `AppSetting` is a key-value store; adding `anthropic_model` requires no schema change.

**Branch:** `feature/anthropic-model-selector` — PR #52

---

## Features

| Feature | Status | Notes |
|---------|--------|-------|
| Model dropdown in Settings (Anthropic section) | Complete | Haiku 4.5 / Sonnet 4.6 / Opus 4.6 |
| Persist selection via AppSetting | Complete | Key: `anthropic_model`, default: `claude-haiku-4-5-20251001` |
| All AI calls use saved model | Complete | `_call_anthropic()` reads from config dict |

---

## Models Available

| Model ID | Label |
|----------|-------|
| `claude-haiku-4-5-20251001` | Haiku 4.5 — Fast & affordable (default) |
| `claude-sonnet-4-6` | Sonnet 4.6 — Balanced |
| `claude-opus-4-6` | Opus 4.6 — Most capable |

---

## File Changes

| File | Action | Summary |
|------|--------|---------|
| `app/ai_provider.py` | Modify | Add `anthropic_model` to `get_ai_config()`; use `config.get('anthropic_model', ...)` in `_call_anthropic()` |
| `app/routes/settings.py` | Modify | Save `anthropic_model` from form POST via `AppSetting.set()` |
| `app/templates/settings/index.html` | Modify | Replace static model label text with `<select>` dropdown |
| `docs/phase-19k-plan.md` | Create | This plan doc |

---

## Verification

- [ ] Go to Settings → AI section with Anthropic selected
- [ ] Confirm dropdown appears with Haiku pre-selected (existing installs unchanged)
- [ ] Switch to Sonnet 4.6, save — use any AI feature and confirm it works
- [ ] Switch back to Haiku, confirm it still works

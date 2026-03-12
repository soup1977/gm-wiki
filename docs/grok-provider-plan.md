# Grok (xAI) AI Provider — Feature Plan

## Status

| Feature | Status | Notes |
|---------|--------|-------|
| `_call_grok()` in `ai_provider.py` | Complete | OpenAI-compatible xAI API |
| `is_ai_enabled()` / `get_available_providers()` updates | Complete | Includes grok |
| `ai_chat()` dispatch | Complete | `elif effective_provider == 'grok'` |
| `get_ai_config()` includes grok fields | Complete | `grok_api_key`, `grok_model` |
| Settings POST saves grok fields | Complete | |
| `/settings/test-grok` route | Complete | Same pattern as test-anthropic |
| Settings UI: Grok radio button | Complete | |
| Settings UI: Grok config section | Complete | API key + model dropdown |
| Settings UI: Grok in per-feature dropdowns | Complete | All 4 feature selects |

## Context

Adds Grok (xAI) as a third AI provider alongside Anthropic and Ollama. The app's architecture was already designed for this — function-based dispatch in `ai_provider.py` and database-stored key-value settings mean no migrations are needed.

Grok's API is OpenAI-compatible, so `_call_grok()` follows the same pattern as the Ollama REST call but hits `https://api.x.ai/v1/chat/completions` with Bearer auth. JSON mode uses `response_format: {type: "json_object"}`.

## Files Modified

| File | Change |
|------|--------|
| `app/ai_provider.py` | `_call_grok()`, updated dispatch, `is_ai_enabled()`, `get_available_providers()`, `get_ai_config()` |
| `app/routes/settings.py` | Save/load `grok_api_key` + `grok_model`; `/settings/test-grok` route |
| `app/templates/settings/index.html` | Grok radio button, config section, Test button, per-feature dropdown options |

No model changes. No migrations. PR #54.

## Grok Models Available

- `grok-3-mini` — Fast & affordable (default)
- `grok-3` — Most capable
- `grok-2-mini`
- `grok-2`

## New Settings Keys

| Key | Default |
|-----|---------|
| `grok_api_key` | `''` |
| `grok_model` | `'grok-3-mini'` |

Keys are auto-created in the `app_settings` key-value table on first save.

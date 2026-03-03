# Campaign Assistant — Link to Story Arc

## Context

The Campaign Assistant creates entities (NPCs, Locations, Quests, Items) with no `story_arc_id`, so arc-aware AI features (Smart Fill, Generate Entry) won't use arc context for them later. The Genesis Wizard handles this automatically, but ad-hoc entities from the assistant are always orphaned. This feature adds a persistent Story Arc selector to the Campaign Assistant chat page.

**Branch:** `feature/assistant-arc-link`

---

## Current State

- `save_entity()` in `campaign_assistant.py:221` creates entities without setting `story_arc_id`
- `story_arc_id` FK already exists on NPC, Location, Quest, Item, and Encounter models
- Campaign Assistant chat page: `app/templates/campaign_assistant/chat.html`
- Campaign Assistant JS: `app/static/js/campaign_assistant.js` (save logic around line 225)

---

## Design

### Persistent Arc Dropdown

Add a Story Arc dropdown at the top of the Campaign Assistant chat page, above the conversation area. This is a "sticky" selector — once the GM picks an arc, all entities created from that conversation are linked to it.

```html
<div class="mb-3">
    <label class="form-label small text-muted">Link new entities to Story Arc (optional)</label>
    <select id="assistant-arc-select" class="form-select form-select-sm bg-dark text-light border-secondary">
        <option value="">— None —</option>
        {% for arc in arcs %}
        <option value="{{ arc.id }}">{{ arc.name }}</option>
        {% endfor %}
    </select>
</div>
```

### Save Flow

1. When the user clicks "Save" on an entity card, the JS reads the current value of `#assistant-arc-select`
2. The `story_arc_id` is included in the POST body to `/api/ai/assistant/save-entity`
3. `save_entity()` in `campaign_assistant.py` reads `data.get('story_arc_id')` and sets it on the entity before commit

### Optional: Arc Context in AI Prompt

When a story arc is selected, inject its name and overview into the system prompt so the AI generates entities that fit the arc's theme. This mirrors what `generate-entry` already does in `ai.py:552-566`.

---

## Files to Modify

| File | Change |
|------|--------|
| `app/routes/campaign_assistant.py` | Pass arcs to template in `chat()` view; read `story_arc_id` in `save_entity()` |
| `app/templates/campaign_assistant/chat.html` | Add Story Arc dropdown above chat area |
| `app/static/js/campaign_assistant.js` | Include `story_arc_id` in save POST body |

**No migration needed** — `story_arc_id` already exists on all entity models.

---

## Implementation Steps

1. In `chat()` route, query `AdventureSite.query.filter_by(campaign_id=campaign.id).all()` and pass as `arcs`
2. Add dropdown to template
3. In `save_entity()`, read `story_arc_id` from request and set on entity (4 entity type blocks)
4. In JS save handler, read `#assistant-arc-select` value and add to POST body
5. (Optional) In `chat_api()`, if arc is selected, inject arc context into system prompt

---

## Verification

1. Open Campaign Assistant with no arc selected → save an entity → `story_arc_id` is NULL (unchanged behavior)
2. Select a Story Arc → save an entity → entity has correct `story_arc_id` in DB
3. Navigate to the saved entity → verify it shows under the correct Story Arc
4. Change arc mid-conversation → next saved entity uses the new arc
5. Arc dropdown only shows arcs for the active campaign

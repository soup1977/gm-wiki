# Phase 15: Dashboard Overhaul

## Feature Status

| Feature | Status | Notes |
|---------|--------|-------|
| Session Mode dashboard | DONE | Phase 12: multi-panel layout, NPC chat, encounters, notes |
| Adventure Site content in dashboard | TODO | **Phase 15a** — collapsible panel with rendered Markdown + ToC |
| Shortcode popup previews | TODO | **Phase 15a** — Bootstrap popover on hover for entity links |
| Pinned entities with inline edit | TODO | Defer to Phase 15b |
| Panel-based layout (Main/Toolkit/Controls) | TODO | **Phase 15b — defer** |
| Map overlay viewer | TODO | **Phase 15b — defer** |
| Dashboard presets ("Combat Mode") | TODO | **Phase 15b — defer** |
| Drag-to-rearrange panels | TODO | **Phase 15b — defer** |

## Notes

Phase 15 is split:
- **15a**: Site content in dashboard + shortcode popup previews — both are independent and buildable now
- **15b**: Panel system + presets + drag-to-rearrange — complex, deferred

---

## Phase 15a: Adventure Site Content in Dashboard

### Goal
When a session has a linked Adventure Site, show its Markdown (rendered) in a collapsible panel inside Session Mode. GM never has to leave the dashboard to read room descriptions.

### Backend Change
**File:** `app/routes/session_mode.py` — `dashboard()` route

```python
active_site = game_session.adventure_sites[0] if game_session.adventure_sites else None
# Pass to template: active_site=active_site
```

### Template Change
**File:** `app/templates/session_mode/dashboard.html`

Add a collapsible card (collapsed by default) in the left column, after existing location info:

```html
{% if active_site %}
<div class="card bg-dark border-secondary mb-3">
    <div class="card-header d-flex justify-content-between align-items-center"
         data-bs-toggle="collapse" data-bs-target="#site-content-panel" style="cursor:pointer;">
        <span><i class="bi bi-map-fill me-2"></i>{{ active_site.name }}</span>
        <i class="bi bi-chevron-down"></i>
    </div>
    <div class="collapse" id="site-content-panel">
        <div class="card-body">
            <nav id="dash-site-toc" class="mb-3 small border-bottom border-secondary pb-2"></nav>
            <div id="dash-site-content" class="markdown-body small">
                {{ active_site.content | md | safe }}
            </div>
        </div>
    </div>
</div>
{% endif %}
```

JS ToC generation reuses the exact same pattern as `adventure_sites/detail.html` lines 176–233 (query `#dash-site-content h2, h3`, build anchor links).

---

## Phase 15a: Shortcode Popup Previews

### Goal
Entity shortcode links (`[npc:42:Aldric]` → `<a href="/npcs/42">Aldric</a>`) show a Bootstrap popover on hover with name, status, and subtitle. No navigation needed for quick reference.

### Step 1 — Data Attributes on Shortcode Links
**File:** `app/shortcode.py`

Change the rendered link output to include `data-preview-type`, `data-preview-id`, and `class="shortcode-link"`:

```python
# Before:
return f'<a href="{url}">{label}</a>'
# After:
return f'<a href="{url}" data-preview-type="{entity_type}" data-preview-id="{entity_id}" class="shortcode-link">{label}</a>'
```

### Step 2 — Preview API Endpoint
**File:** `app/routes/entity_search.py`

```
GET /entity-preview/<string:entity_type>/<int:entity_id>
Response: { "name": "...", "subtitle": "...", "status": "..." }
```

Fetch entity by type using a dispatch dict (same `TYPE_CONFIG` structure as `shortcode.py`). Supported types: `npc`, `location`, `quest`, `item`, `site`.

### Step 3 — Popover JS
**File:** `app/static/js/shortcode_preview.js` (new, ~50 lines)

```js
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('a.shortcode-link').forEach(function (link) {
        link.addEventListener('mouseenter', function () {
            if (this._popoverLoaded) return;
            fetch('/entity-preview/' + this.dataset.previewType + '/' + this.dataset.previewId)
                .then(r => r.json())
                .then(data => {
                    new bootstrap.Popover(this, {
                        title: data.name,
                        content: (data.subtitle || '') + (data.status ? ' · ' + data.status : ''),
                        trigger: 'hover focus',
                        placement: 'top'
                    }).show();
                    this._popoverLoaded = true;
                })
                .catch(() => {});
        });
    });
});
```

Load in `app/templates/base.html` after Bootstrap JS. Does nothing if no shortcode links exist on the page.

---

## Files Modified (Phase 15a)

| File | Changes |
|------|---------|
| `app/routes/session_mode.py` | Pass `active_site` to dashboard template |
| `app/templates/session_mode/dashboard.html` | Site content collapsible panel + JS ToC |
| `app/shortcode.py` | Add `data-preview-type/id` + `shortcode-link` class |
| `app/routes/entity_search.py` | New `/entity-preview/<type>/<id>` endpoint |
| `app/static/js/shortcode_preview.js` | New file — hover popover JS |
| `app/templates/base.html` | Load `shortcode_preview.js` |

No migrations needed.

## Verification

1. Session Mode with linked Adventure Site → Site Content card visible (collapsed) → expand → rendered Markdown + ToC
2. Any page with shortcode links → hover a link → popover shows name + status
3. Pages with no shortcode links → no JS errors

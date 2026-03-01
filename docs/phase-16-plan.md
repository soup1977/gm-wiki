# Phase 16: Workflow Guidance

## Feature Status

| Feature | Status | Notes |
|---------|--------|-------|
| "Start Session Here" button | DONE | Phase 12: on Adventure Site detail |
| "Save & Start Next Session" button | DONE | Phase 12: on post-session wrap-up |
| Session carryover | DONE | Phase 12: entities carried to next session |
| Campaign setup wizard | TODO | Feature 1 below |
| Adventure planning checklist | TODO | Feature 2 below |
| Campaign entity grouping view | TODO | Feature 3 below |
| "Next Step" transition buttons | PARTIAL | Feature 4 below — quests + NPCs missing |
| Theme engine | FUTURE | Deferred — see docs/future-ideas.md |

## Notes

Phase 16 does NOT depend on Phase 15. All 4 features are independent and can be built in any order.

The originally planned "high-contrast theme toggle" is intentionally deferred in favor of building a proper theme engine (named themes, CSS variable sets, user-selectable). Details in `docs/future-ideas.md`.

---

## Feature 1: Campaign Setup Wizard

### Goal
Break the campaign create form into 3 labelled steps so first-time setup feels guided. Edit form stays unchanged.

### Implementation
**Files:** `app/templates/campaigns/form.html`, `app/routes/campaigns.py`

Pass `is_create=True` from `create_campaign()` and `is_create=False` from `edit_campaign()`. The wizard only activates when `is_create=True` (detected via Jinja variable in the template).

Wrap form fields in `<div class="wizard-step">` sections. JS controls show/hide and a Bootstrap progress bar:

- **Step 1 — The Basics:** Name, System, Status
- **Step 2 — World Context:** Description + AI World Context textarea
- **Step 3 — Customize:** Stat preset + Image style prompt + Submit button

Back/Next buttons are inline JS. Submit button only visible on step 3. The form `action` and POST handling are unchanged.

---

## Feature 2: Adventure Planning Checklist

### Goal
In the Adventure Site editor sidebar, show a checklist of planning best-practices. Static HTML — no backend or form submission.

### Implementation
**File:** `app/templates/adventure_sites/form.html`

Add a new accordion item in the right-column sidebar (after the existing "Writing Tips" accordion):

```html
<div class="accordion-item bg-dark border-secondary">
    <h2 class="accordion-header">
        <button class="accordion-button collapsed bg-dark text-light" type="button"
                data-bs-toggle="collapse" data-bs-target="#planning-checklist">
            <i class="bi bi-check2-square me-2"></i> Planning Checklist
        </button>
    </h2>
    <div id="planning-checklist" class="accordion-collapse collapse">
        <div class="accordion-body py-2 px-3">
            <ul class="list-unstyled mb-0 small">
                <li><input type="checkbox" class="form-check-input me-2"> Entry/exit points defined</li>
                <li><input type="checkbox" class="form-check-input me-2"> At least one keyed NPC</li>
                <li><input type="checkbox" class="form-check-input me-2"> Boss encounter or climax</li>
                <li><input type="checkbox" class="form-check-input me-2"> Non-combat challenge</li>
                <li><input type="checkbox" class="form-check-input me-2"> Unique environmental detail</li>
                <li><input type="checkbox" class="form-check-input me-2"> Loot/reward defined</li>
                <li><input type="checkbox" class="form-check-input me-2"> Linked to campaign NPCs</li>
            </ul>
        </div>
    </div>
</div>
```

Checkboxes are visual aids only (not submitted). Use localStorage keyed to `'checklist_' + siteId` for persistence across edits.

---

## Feature 3: Campaign Entity Grouping View

### Goal
On the Campaign detail page, add JS filter tabs to the NPCs and Quests cards so the GM can focus on "Active Quests" or "Alive NPCs" without navigating away.

### Implementation
**File:** `app/templates/campaigns/detail.html`

Add `data-status` attributes to each `<li>` in the NPCs and Quests lists. Add a Bootstrap button-group filter row above each list.

**NPCs:** Tabs — All / Alive / Dead / Missing
**Quests:** Tabs — All / Active / Completed / Failed

```html
<div class="btn-group btn-group-sm mb-2">
    <button class="btn btn-outline-secondary active" onclick="filterList('npc-list', 'all', this)">All</button>
    <button class="btn btn-outline-secondary" onclick="filterList('npc-list', 'alive', this)">Alive</button>
    <button class="btn btn-outline-secondary" onclick="filterList('npc-list', 'dead', this)">Dead</button>
    <button class="btn btn-outline-secondary" onclick="filterList('npc-list', 'missing', this)">Missing</button>
</div>
<ul id="npc-list" class="list-unstyled mb-0">
    {% for npc in campaign.npcs %}  {# remove [:8] limit — JS handles display #}
    <li data-status="{{ npc.status }}">...</li>
    {% endfor %}
</ul>
```

Inline JS at bottom of template:
```js
function filterList(listId, status, btn) {
    document.querySelectorAll('#' + listId + ' li').forEach(function(li) {
        li.style.display = (status === 'all' || li.dataset.status === status) ? '' : 'none';
    });
    btn.closest('.btn-group').querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
}
// On load: hide excess items for "All" tab (keep 8-item limit behavior)
```

---

## Feature 4: "Next Step" Transition Buttons

### Goal
Add quick-action status-change buttons on Quest and NPC detail pages so the GM can update status without opening the full edit form.

### Backend
**File:** `app/routes/quests.py` — add:
```python
@quests_bp.route('/<int:quest_id>/set-status', methods=['POST'])
@login_required
def set_status(quest_id):
    quest = Quest.query.get_or_404(quest_id)
    quest.status = request.form.get('status', quest.status)
    db.session.commit()
    return redirect(url_for('quests.quest_detail', quest_id=quest_id))
```

**File:** `app/routes/npcs.py` — same pattern for NPC status.

### Templates

**`app/templates/quests/detail.html`** — add below the quest title/status badge:
```html
<div class="d-flex gap-2 mt-2 flex-wrap">
    {% if quest.status != 'active' %}
    <form method="POST" action="{{ url_for('quests.set_status', quest_id=quest.id) }}">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="hidden" name="status" value="active">
        <button class="btn btn-sm btn-outline-success">Set Active</button>
    </form>
    {% endif %}
    {% if quest.status not in ('completed', 'failed') %}
    <form method="POST" action="{{ url_for('quests.set_status', quest_id=quest.id) }}">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="hidden" name="status" value="completed">
        <button class="btn btn-sm btn-outline-secondary">Complete</button>
    </form>
    <form method="POST" action="{{ url_for('quests.set_status', quest_id=quest.id) }}">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="hidden" name="status" value="failed">
        <button class="btn btn-sm btn-outline-danger">Fail</button>
    </form>
    {% endif %}
</div>
```

**`app/templates/npcs/detail.html`** — same pattern for NPC status (alive / dead / missing / unknown).

---

## Files Modified

| File | Changes |
|------|---------|
| `app/templates/campaigns/form.html` | Wizard step divs, progress bar, Next/Back/Submit JS |
| `app/routes/campaigns.py` | Pass `is_create` flag to template |
| `app/templates/adventure_sites/form.html` | Planning checklist accordion item in sidebar |
| `app/templates/campaigns/detail.html` | Filter button groups + data-status attrs + inline JS |
| `app/routes/quests.py` | `POST /quests/<id>/set-status` endpoint |
| `app/routes/npcs.py` | `POST /npcs/<id>/set-status` endpoint |
| `app/templates/quests/detail.html` | Quick-status buttons in header area |
| `app/templates/npcs/detail.html` | Quick-status buttons in header area |

No migrations needed — no new models.

**Also created:** `docs/future-ideas.md` — theme engine idea documented for future planning.

## Verification

1. Campaign create → wizard with progress bar, Back/Next, submit only on step 3; Edit campaign → no wizard (normal form)
2. Adventure Site editor → sidebar shows "Planning Checklist" accordion; check items, reopen page → state persists (localStorage)
3. Campaign detail → NPCs card has All/Alive/Dead/Missing tabs; click "Dead" → only dead NPCs shown; Quests tabs filter by status
4. Quest detail → context-sensitive status buttons; click "Complete" → status updates, redirects back
5. NPC detail → "Mark Dead" / "Mark Missing" buttons; click → status updates
6. `docs/future-ideas.md` exists and contains the Theme Engine idea

# Phase 18: Arc-Session Workflow

## Context

A Story Arc is a **self-contained blueprint for one storyline within a campaign** — not the whole campaign. A campaign may have a small number of concurrent arcs (typically 1-3, occasionally more). Each arc has its own NPCs, Locations, Quests, Items, and Encounters.

When a GM hits "Start Session Here" on an arc, they want to pull from that arc's entity pool to populate tonight's session — but they're not limited to that arc. They can also grab entities from other arcs or the campaign at large.

**Current gaps this phase fixes:**

1. **Encounters have no story_arc_id** — encounters created through the Genesis Wizard aren't linked to the arc, so they can't be surfaced as arc-relevant when starting a session.
2. **The arc document is thin** — Genesis only populates Overview + Hook. Milestones exist only as sidebar checkboxes, not as runnable sections in the document.
3. **"Start Session Here" does almost nothing** — it pre-selects the arc in the dropdown but doesn't pre-check any of the arc's NPCs, locations, quests, or encounters.
4. **Encounters aren't on the session form** — there's no way to link encounters to a session at creation time.

---

## Feature Table

| Feature | Status | Notes |
|---------|--------|-------|
| story_arc_id on Encounter model | TODO | Migration required |
| Remove encounter guard in genesis_create_entity | TODO | Depends on migration |
| Richer arc content (milestones as sections) | TODO | genesis_save() change only |
| Encounters on session form | TODO | create + edit session forms |
| Arc-aware session prefill + banner | TODO | Depends on encounters on form |

---

## Feature 1: story_arc_id on Encounter Model

**Changes:**
- `app/models.py`: Add `story_arc_id = db.Column(db.Integer, db.ForeignKey('adventure_site.id'), nullable=True)` to `Encounter`
- Add `story_arc = db.relationship('AdventureSite', backref='arc_encounters')` to `Encounter`
- New migration: `migrations/versions/j0k1l2m3n4o5_add_story_arc_id_to_encounters.py`
  - Revision ID: `j0k1l2m3n4o5` | Down revision: `i9j0k1l2m3n4`
  - `ALTER TABLE encounters ADD COLUMN story_arc_id INTEGER REFERENCES adventure_site(id)`
- `app/routes/ai.py`: In `genesis_create_entity()`, remove the 'encounter' exclusion from the `story_arc_id` guard

---

## Feature 2: Richer Arc Content from Genesis Wizard

`genesis_save()` in `app/routes/adventure_sites.py` — new content structure:

```
## Overview
{premise}

## Hook
{hook}

## Themes
{themes}

---

## Milestone 1 — {label}

## Milestone 2 — {label}
...
```

- Themes becomes a `##` section (not inline bold)
- Each milestone becomes a `##` section with an empty body for GM to fill in
- Sidebar milestone checkboxes are unchanged — they still read from the JSON field
- No AI prompt changes needed

---

## Feature 3: Encounters on the Session Form

**Encounter linking model:** `session_id` FK on Encounter (nullable, one-to-many). An encounter is "available" when `session_id IS NULL`. Assigning it to a session sets `session_id`. One encounter runs in one session.

**`app/routes/sessions.py` changes:**
- `create_session()`: load `encounters = Encounter.query.filter_by(campaign_id=campaign_id, session_id=None).order_by(Encounter.name).all()`
- `edit_session()`: load encounters where `session_id IS NULL OR session_id = sess.id`
- POST handler: `encounter_ids = request.form.getlist('encounters_planned')`, set `session_id = sess.id` on selected; clear to `None` on deselected previously-linked encounters
- Pass `encounters` to template in both routes

**`app/templates/sessions/form.html` changes:**
- Add multi-select section for "Encounters" (same Bootstrap pattern as NPCs, Locations, Quests)
- Place after Quests Touched, before Items Mentioned
- Each option: encounter name + type badge
- Pre-select encounters linked to this session (edit) or arc encounters (create, via `arc_encounter_ids`)

---

## Feature 4: Arc-Aware Session Prefill

**`app/routes/sessions.py` — `create_session()` additions after `preselect_site_id` is read:**

```python
arc_npc_ids = set()
arc_location_ids = set()
arc_quest_ids = set()
arc_encounter_ids = set()
arc_site = None
arc_next_milestone = None

if preselect_site_id:
    arc_site = AdventureSite.query.filter_by(id=preselect_site_id, campaign_id=campaign_id).first()
    if arc_site:
        arc_npc_ids       = {n.id for n in NPC.query.filter_by(campaign_id=campaign_id, story_arc_id=preselect_site_id).all()}
        arc_location_ids  = {l.id for l in Location.query.filter_by(campaign_id=campaign_id, story_arc_id=preselect_site_id).all()}
        arc_quest_ids     = {q.id for q in Quest.query.filter_by(campaign_id=campaign_id, story_arc_id=preselect_site_id).all()}
        arc_encounter_ids = {e.id for e in Encounter.query.filter_by(campaign_id=campaign_id, story_arc_id=preselect_site_id, session_id=None).all()}
        for m in arc_site.get_milestones():
            if not m.get('done'):
                arc_next_milestone = m['label']
                break
```

Pass `arc_npc_ids`, `arc_location_ids`, `arc_quest_ids`, `arc_encounter_ids`, `arc_site`, `arc_next_milestone` to template.

**`app/templates/sessions/form.html` additions:**

Arc banner (above the form fields, when `arc_site` is set):
```html
<div class="alert alert-info mb-4">
  <i class="bi bi-map me-1"></i> <strong>Starting session for: {{ arc_site.name }}</strong>
  {% if arc_next_milestone %} — Working toward: <em>{{ arc_next_milestone }}</em>{% endif %}
  <br><small class="text-muted">Arc entities are pre-selected below. Deselect anything you won't need tonight.</small>
</div>
```

Updated `selected` logic in each multi-select `<option>`:
- NPCs: `{% if (sess and npc in sess.npcs_featured) or npc.id in arc_npc_ids or (carryover and npc.id in carryover.npc_ids) %}selected{% endif %}`
- Locations: same with `arc_location_ids`
- Quests: same with `arc_quest_ids`
- Encounters: `{% if (sess and enc in sess.encounters) or enc.id in arc_encounter_ids %}selected{% endif %}`

---

## Critical Files

| File | Change |
|------|--------|
| `app/models.py` | Add `story_arc_id` FK + relationship to `Encounter` |
| `migrations/versions/j0k1l2m3n4o5_add_story_arc_id_to_encounters.py` | New migration |
| `app/routes/ai.py` | Remove 'encounter' exclusion from `story_arc_id` guard |
| `app/routes/adventure_sites.py` | Update `genesis_save()` — Themes section + milestone sections |
| `app/routes/sessions.py` | Encounter loading + arc prefill sets in `create_session()` and `edit_session()` |
| `app/templates/sessions/form.html` | Encounters multi-select + arc banner + arc prefill pre-selection |

---

## Implementation Order

1. Migration + model change (Feature 1)
2. Remove encounter guard in ai.py (Feature 1 completion)
3. Richer arc content in genesis_save() (Feature 2) — standalone
4. Add encounters to session form (Feature 3)
5. Arc-aware prefill + banner (Feature 4)

---

## Verification

1. `FLASK_APP=run.py python3 -m flask db upgrade` — migration applies cleanly
2. Story Arcs → Create with AI, generate arc with encounters included
3. Confirm encounters appear in arc's Linked Entities tab
4. Open arc detail — `## Milestone 1 —` sections appear in content
5. Click "Start Session Here"
6. Confirm banner shows arc name + next incomplete milestone
7. Confirm arc NPCs, locations, quests, encounters are all pre-selected
8. Deselect one entity, save — only selected ones are linked
9. Session detail — encounters appear
10. Deploy: `bash /mnt/user/appdata/gm-wiki/update.sh`

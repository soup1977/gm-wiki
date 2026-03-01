/**
 * genesis_wizard.js — Phase 17 Story Arc Genesis Wizard
 *
 * Manages all four wizard steps client-side:
 *   Step 1: Seed input  → POST /api/ai/generate-arc-structure
 *   Step 2: Review arc  → POST /api/ai/propose-arc-entities
 *   Step 3: Bundle      → POST /sites/genesis/save + loop POST /api/ai/genesis-create-entity
 *   Step 4: Progress
 */

const PROGRESS_PCT = { 1: 25, 2: 50, 3: 75, 4: 100 };

// State shared between steps
const wizard = {
    currentStep: 1,
    arcData:     {},   // filled by Step 1 AI call
    siteId:      null, // filled when arc is saved at start of Step 4
    entities:    [],   // checked entities from Step 3 bundle
};

// ── Step navigation ────────────────────────────────────────────────────────

function showStep(n) {
    document.querySelectorAll('.wizard-step').forEach(el => el.classList.add('d-none'));
    document.getElementById('step-' + n).classList.remove('d-none');
    document.getElementById('step-num').textContent = n;
    const bar = document.getElementById('wizard-progress');
    bar.style.width = PROGRESS_PCT[n] + '%';
    bar.setAttribute('aria-valuenow', PROGRESS_PCT[n]);
    wizard.currentStep = n;
    window.scrollTo(0, 0);
}

// ── CSRF helper ────────────────────────────────────────────────────────────

function getCsrf() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
}

// ── Step 1 → Step 2: generate arc structure ────────────────────────────────

async function generateArcStructure() {
    const seedText = document.getElementById('seed_text').value.trim();
    if (!seedText) {
        document.getElementById('seed_text').classList.add('is-invalid');
        document.getElementById('seed_text').focus();
        return;
    }
    document.getElementById('seed_text').classList.remove('is-invalid');

    const btn = document.getElementById('btn-generate-arc');
    setLoading(btn, true, 'Generating arc...');

    const payload = {
        seed_text: seedText,
        conflict:  document.getElementById('guided_conflict').value.trim(),
        villain:   document.getElementById('guided_villain').value.trim(),
        location:  document.getElementById('guided_location').value.trim(),
        hook:      document.getElementById('guided_hook').value.trim(),
        stakes:    document.getElementById('guided_stakes').value.trim(),
    };

    try {
        const resp = await apiPost('/api/ai/generate-arc-structure', payload);
        if (resp.error) { showError('step1-error', resp.error); return; }

        // Populate Step 2 fields with AI-returned data
        setVal('arc_title',      resp.title      || '');
        setVal('arc_subtitle',   resp.subtitle   || '');
        setVal('arc_premise',    resp.premise    || '');
        setVal('arc_hook',       resp.hook       || '');
        setVal('arc_themes',     resp.themes     || '');
        setVal('arc_sessions',   resp.estimated_sessions || '');

        // Populate milestones (array → one per line in textarea)
        const milestones = resp.milestones || [];
        setVal('arc_milestones', Array.isArray(milestones) ? milestones.join('\n') : milestones);

        // Stash arc data for later
        wizard.arcData = resp;

        showStep(2);
    } catch (err) {
        showError('step1-error', 'Request failed: ' + err.message);
    } finally {
        setLoading(btn, false, '<i class="bi bi-stars"></i> Generate Story Arc');
    }
}

// ── Step 2 → Step 3: propose entity bundle ─────────────────────────────────

async function proposeEntities() {
    // Collect updated arc data from editable Step 2 fields
    wizard.arcData = {
        title:              getVal('arc_title'),
        subtitle:           getVal('arc_subtitle'),
        premise:            getVal('arc_premise'),
        hook:               getVal('arc_hook'),
        themes:             getVal('arc_themes'),
        estimated_sessions: getVal('arc_sessions'),
        milestones:         getVal('arc_milestones').split('\n').map(s => s.trim()).filter(Boolean),
    };

    const btn = document.getElementById('btn-propose-entities');
    setLoading(btn, true, 'Proposing entities...');
    clearError('step2-error');

    try {
        const resp = await apiPost('/api/ai/propose-arc-entities', {
            arc_title:   wizard.arcData.title,
            arc_premise: wizard.arcData.premise,
            arc_content: wizard.arcData.premise + '\n' + wizard.arcData.hook,
        });
        if (resp.error) { showError('step2-error', resp.error); return; }

        renderEntityBundle(resp);
        showStep(3);
    } catch (err) {
        showError('step2-error', 'Request failed: ' + err.message);
    } finally {
        setLoading(btn, false, 'Propose Entities <i class="bi bi-arrow-right"></i>');
    }
}

// ── Render Step 3 entity bundle ────────────────────────────────────────────

const ENTITY_LABELS = {
    npcs:       { label: 'NPCs',       icon: 'bi-person-fill',       color: 'info' },
    locations:  { label: 'Locations',  icon: 'bi-geo-alt-fill',      color: 'success' },
    quests:     { label: 'Quests',     icon: 'bi-map-fill',          color: 'warning' },
    items:      { label: 'Items',      icon: 'bi-gem',               color: 'secondary' },
    encounters: { label: 'Encounters', icon: 'bi-shield-fill-exclamation', color: 'danger' },
};

function renderEntityBundle(bundle) {
    const container = document.getElementById('entity-bundle');
    container.innerHTML = '';

    // encounters and items collapsed by default
    const COLLAPSED_BY_DEFAULT = ['items', 'encounters'];

    let totalCount = 0;
    for (const [type, meta] of Object.entries(ENTITY_LABELS)) {
        const items = bundle[type] || [];
        if (!items.length) continue;

        // "items" and "encounters" go in a collapsible section
        const isOptional = COLLAPSED_BY_DEFAULT.includes(type);
        const collapseId = `collapse-${type}`;

        const section = document.createElement('div');
        section.className = 'mb-3';

        const header = document.createElement('div');
        header.className = 'd-flex align-items-center gap-2 mb-2';
        if (isOptional) {
            header.innerHTML = `
                <button class="btn btn-sm btn-outline-secondary" type="button"
                        data-bs-toggle="collapse" data-bs-target="#${collapseId}">
                    <i class="bi ${meta.icon} text-${meta.color}"></i> ${meta.label}
                    <span class="badge bg-secondary">${items.length}</span>
                    <i class="bi bi-chevron-down small"></i>
                </button>
                <span class="text-muted small fst-italic">optional</span>`;
        } else {
            header.innerHTML = `
                <i class="bi ${meta.icon} text-${meta.color}"></i>
                <strong>${meta.label}</strong>
                <span class="badge bg-secondary">${items.length}</span>`;
        }
        section.appendChild(header);

        const cardWrapper = document.createElement('div');
        cardWrapper.id = isOptional ? collapseId : `section-${type}`;
        if (isOptional) cardWrapper.className = 'collapse';

        items.forEach((item, idx) => {
            const entityType = type === 'npcs' ? 'npc' :
                               type === 'encounters' ? 'encounter' :
                               type.slice(0, -1); // locations→location, quests→quest, items→item

            const card = document.createElement('div');
            card.className = 'card mb-2 bg-dark border-secondary';
            const checkId = `entity-${type}-${idx}`;
            const desc = item.description || item.hook || '';
            const roleBadge = item.role ? `<span class="badge bg-secondary me-1">${item.role}</span>` : '';
            const typeBadge = item.type ? `<span class="badge bg-secondary me-1">${item.type}</span>` : '';

            card.innerHTML = `
                <div class="card-body py-2 px-3">
                    <div class="d-flex align-items-start gap-2">
                        <input class="form-check-input mt-1 flex-shrink-0" type="checkbox"
                               id="${checkId}" checked
                               data-entity-type="${entityType}"
                               data-entity-name="${escapeHtml(item.name)}"
                               data-entity-desc="${escapeHtml(desc)}">
                        <div class="flex-grow-1">
                            <div class="d-flex align-items-center gap-1 mb-1">
                                <input type="text" class="form-control form-control-sm bg-dark text-light border-secondary entity-name-input"
                                       value="${escapeHtml(item.name)}"
                                       data-checkbox-id="${checkId}"
                                       style="max-width:220px;">
                                ${roleBadge}${typeBadge}
                            </div>
                            <div class="text-muted small">${escapeHtml(desc)}</div>
                        </div>
                    </div>
                </div>`;
            cardWrapper.appendChild(card);
            totalCount++;
        });

        section.appendChild(cardWrapper);
        container.appendChild(section);
    }

    // Update the "Generate X entities" button label
    document.getElementById('btn-generate-all').textContent = `Generate all checked entities`;
    updateGenerateButtonCount();

    // Update count dynamically when checkboxes change
    container.addEventListener('change', updateGenerateButtonCount);

    // Keep name inputs in sync with checkbox data attributes
    container.querySelectorAll('.entity-name-input').forEach(input => {
        input.addEventListener('input', function() {
            const cb = document.getElementById(this.dataset.checkboxId);
            if (cb) cb.dataset.entityName = this.value;
        });
    });
}

function updateGenerateButtonCount() {
    const checked = document.querySelectorAll('#entity-bundle input[type=checkbox]:checked').length;
    const btn = document.getElementById('btn-generate-all');
    btn.textContent = checked > 0
        ? `Generate ${checked} entit${checked === 1 ? 'y' : 'ies'}`
        : 'No entities selected';
    btn.disabled = checked === 0;
}

// ── Step 3 → Step 4: save arc + generate all entities ─────────────────────

async function startGeneration() {
    // Collect checked entities
    const checked = [...document.querySelectorAll('#entity-bundle input[type=checkbox]:checked')];
    if (!checked.length) return;

    wizard.entities = checked.map(cb => ({
        entity_type: cb.dataset.entityType,
        concept:     `${cb.dataset.entityName}: ${cb.dataset.entityDesc}`,
        name:        cb.dataset.entityName,
    }));

    showStep(4);
    clearError('step4-error');

    const progressBar   = document.getElementById('gen-progress-bar');
    const progressLabel = document.getElementById('gen-progress-label');
    const resultsList   = document.getElementById('gen-results');
    resultsList.innerHTML = '';

    // ── Save the Story Arc first ───────────────────────────────────────────
    progressLabel.textContent = 'Saving Story Arc…';
    progressBar.style.width = '5%';

    try {
        const saveResp = await apiPost('/sites/genesis/save', wizard.arcData);
        if (saveResp.error) { showError('step4-error', saveResp.error); return; }
        wizard.siteId = saveResp.site_id;

        // Add arc link to results
        addResultItem(resultsList, 'adventure_site', saveResp.name,
                      `/sites/${saveResp.site_id}`, true);
    } catch (err) {
        showError('step4-error', 'Failed to save Story Arc: ' + err.message);
        return;
    }

    // ── Generate entities one by one ──────────────────────────────────────
    const total = wizard.entities.length;
    for (let i = 0; i < total; i++) {
        const ent = wizard.entities[i];
        const pct = Math.round(10 + ((i + 1) / total) * 90);
        progressBar.style.width = pct + '%';
        progressLabel.textContent = `Creating ${ent.name}… (${i + 1} of ${total})`;

        try {
            const resp = await apiPost('/api/ai/genesis-create-entity', {
                entity_type:  ent.entity_type,
                concept:      ent.concept,
                story_arc_id: wizard.siteId,
            });
            if (resp.error) {
                addResultItem(resultsList, ent.entity_type, ent.name, null, false, resp.error);
            } else {
                addResultItem(resultsList, resp.entity_type, resp.name, resp.url, false);
            }
        } catch (err) {
            addResultItem(resultsList, ent.entity_type, ent.name, null, false, err.message);
        }
    }

    progressBar.style.width = '100%';
    progressLabel.textContent = 'Done!';
    progressBar.classList.remove('progress-bar-animated');

    // Show the "View Story Arc" button
    document.getElementById('btn-view-arc').href = `/sites/${wizard.siteId}`;
    document.getElementById('arc-complete-panel').classList.remove('d-none');
}

function addResultItem(list, entityType, name, url, isArc, errorMsg) {
    const icon = isArc         ? 'bi-map-fill text-warning' :
                 entityType === 'npc'       ? 'bi-person-fill text-info' :
                 entityType === 'location'  ? 'bi-geo-alt-fill text-success' :
                 entityType === 'quest'     ? 'bi-map-fill text-warning' :
                 entityType === 'item'      ? 'bi-gem text-secondary' :
                                             'bi-shield-fill text-danger';
    const li = document.createElement('li');
    li.className = 'list-group-item bg-dark text-light border-secondary d-flex align-items-center gap-2';
    if (errorMsg) {
        li.innerHTML = `<i class="bi bi-x-circle text-danger"></i>
                        <span class="text-muted">${escapeHtml(name)}</span>
                        <span class="text-danger small ms-auto">${escapeHtml(errorMsg)}</span>`;
    } else {
        li.innerHTML = `<i class="bi ${icon}"></i>
                        <a href="${url}" class="text-decoration-none text-light">${escapeHtml(name)}</a>
                        <i class="bi bi-check-circle text-success ms-auto"></i>`;
    }
    list.appendChild(li);
}

// ── Utilities ──────────────────────────────────────────────────────────────

async function apiPost(url, body) {
    const resp = await fetch(url, {
        method:  'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken':  getCsrf(),
        },
        body: JSON.stringify(body),
    });
    return resp.json();
}

function setVal(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value;
}

function getVal(id) {
    const el = document.getElementById(id);
    return el ? el.value.trim() : '';
}

function setLoading(btn, loading, label) {
    btn.disabled = loading;
    if (loading) {
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>' + label;
    } else {
        btn.innerHTML = label;
    }
}

function showError(containerId, msg) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.textContent = msg;
    el.classList.remove('d-none');
}

function clearError(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.textContent = '';
    el.classList.add('d-none');
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ── Pre-fill seed from URL param (e.g. launched from brainstorm results) ───

(function () {
    const seed = new URLSearchParams(window.location.search).get('seed');
    if (seed) {
        const el = document.getElementById('seed_text');
        if (el) el.value = seed;
    }
}());

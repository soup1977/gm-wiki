/**
 * adventure_builder.js — Draft Review UI for Phase 20
 *
 * Reads the AI-generated adventure draft from sessionStorage,
 * renders it as a tree (Acts → Scenes → Rooms), and lets the GM
 * click any room to edit it inline before saving.
 */

let draft = null;           // The full adventure JSON from AI
let currentRoomPath = null; // { actIdx, sceneIdx, roomIdx }

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', function () {
    const raw = sessionStorage.getItem('adventure_draft');
    if (!raw) {
        document.getElementById('no-draft').style.display = '';
        return;
    }

    try {
        draft = JSON.parse(raw);
    } catch (e) {
        document.getElementById('no-draft').style.display = '';
        return;
    }

    document.getElementById('draft-content').style.display = '';
    renderDraft();
});

// ---------------------------------------------------------------------------
// Render the full draft tree
// ---------------------------------------------------------------------------

function renderDraft() {
    document.getElementById('preview-title').textContent = draft.title || 'Adventure Draft';
    document.getElementById('preview-tagline').textContent = draft.tagline || '';
    document.getElementById('preview-hook').textContent = draft.hook || '—';
    document.getElementById('preview-premise').textContent = draft.premise || '—';
    document.getElementById('preview-system').textContent = (draft.system_hint || 'generic').toUpperCase();

    renderActs();
    renderNpcs();
    renderFactions();
}

function renderActs() {
    const container = document.getElementById('acts-container');
    container.innerHTML = '';

    (draft.acts || []).forEach((act, actIdx) => {
        const actEl = document.createElement('div');
        actEl.className = 'card border-secondary bg-dark mb-3';
        actEl.innerHTML = `
            <div class="card-header act-header border-secondary d-flex justify-content-between align-items-center py-2">
                <span class="fw-bold">
                    <span class="text-warning me-2">Act ${act.number || actIdx + 1}</span>${escHtml(act.title || '')}
                </span>
                <button class="btn btn-sm btn-outline-secondary" onclick="addScene(${actIdx})">
                    <i class="bi bi-plus"></i> Scene
                </button>
            </div>
            ${act.description ? `<div class="card-body py-2 border-bottom border-secondary"><small class="text-muted">${escHtml(act.description)}</small></div>` : ''}
            <div class="card-body py-2 scenes-container" id="scenes-act-${actIdx}"></div>`;
        container.appendChild(actEl);

        renderScenes(actIdx, actEl.querySelector(`#scenes-act-${actIdx}`));
    });
}

function renderScenes(actIdx, container) {
    const scenes = (draft.acts[actIdx] || {}).scenes || [];
    container.innerHTML = '';

    scenes.forEach((scene, sceneIdx) => {
        const sceneEl = document.createElement('div');
        sceneEl.className = 'mb-2';
        sceneEl.innerHTML = `
            <div class="scene-header rounded px-2 py-1 mb-2 d-flex justify-content-between align-items-center">
                <span class="fw-semibold text-info">
                    <i class="bi bi-geo-alt me-1"></i>${escHtml(scene.title || 'Scene')}
                    ${scene.scene_type ? `<small class="text-muted ms-1">(${escHtml(scene.scene_type)})</small>` : ''}
                </span>
                <button class="btn btn-sm btn-outline-secondary py-0" onclick="addRoom(${actIdx}, ${sceneIdx})">
                    <i class="bi bi-plus"></i> Room
                </button>
            </div>
            <div id="rooms-${actIdx}-${sceneIdx}"></div>`;
        container.appendChild(sceneEl);

        renderRooms(actIdx, sceneIdx, sceneEl.querySelector(`#rooms-${actIdx}-${sceneIdx}`));
    });
}

function renderRooms(actIdx, sceneIdx, container) {
    const rooms = ((draft.acts[actIdx] || {}).scenes || [])[sceneIdx]?.rooms || [];
    container.innerHTML = '';

    rooms.forEach((room, roomIdx) => {
        const system = draft.system_hint || 'generic';
        const creatureBadges = (room.creatures || []).map(c => {
            let stat = '';
            if (system === 'icrpg' && c.hearts) stat = ` ❤️×${c.hearts}`;
            else if (c.hp) stat = ` ${c.hp}HP`;
            return `<span class="badge bg-dark border border-secondary me-1" style="font-size:.7rem">💀 ${escHtml(c.name)}${stat}</span>`;
        }).join('');

        const lootBadges = (room.loot || []).map(l =>
            `<span class="badge bg-dark border border-warning me-1" style="font-size:.7rem">🗝 ${escHtml(l.name)}</span>`
        ).join('');

        const roomEl = document.createElement('div');
        roomEl.className = 'card border-secondary bg-dark mb-2 room-card';
        roomEl.dataset.actIdx = actIdx;
        roomEl.dataset.sceneIdx = sceneIdx;
        roomEl.dataset.roomIdx = roomIdx;
        roomEl.style.cursor = 'pointer';
        roomEl.innerHTML = `
            <div class="card-body py-2 px-3">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <span class="room-key me-2">${escHtml(room.key || '—')}</span>
                        <span class="fw-semibold">${escHtml(room.title || 'Room')}</span>
                    </div>
                    <button class="btn btn-sm btn-link text-danger p-0 ms-2 delete-room-btn"
                            onclick="deleteRoom(event, ${actIdx}, ${sceneIdx}, ${roomIdx})">✕</button>
                </div>
                ${room.read_aloud ? `<div class="read-aloud-preview small mt-1 ps-2 border-start border-info">${escHtml(room.read_aloud.substring(0, 100))}${room.read_aloud.length > 100 ? '…' : ''}</div>` : ''}
                ${(creatureBadges || lootBadges) ? `<div class="mt-1">${creatureBadges}${lootBadges}</div>` : ''}
            </div>`;
        roomEl.addEventListener('click', (e) => {
            if (e.target.closest('.delete-room-btn')) return;
            openEditor(actIdx, sceneIdx, roomIdx);
        });
        container.appendChild(roomEl);
    });
}

function renderNpcs() {
    const el = document.getElementById('npcs-list');
    const npcs = draft.key_npcs || [];
    if (!npcs.length) { el.innerHTML = '<small class="text-muted">None specified</small>'; return; }
    el.innerHTML = npcs.map(n => `
        <div class="mb-1 small">
            <span class="fw-semibold">${escHtml(n.name || '')}</span>
            ${n.role ? `<span class="text-muted ms-1">— ${escHtml(n.role)}</span>` : ''}
            ${n.notes ? `<div class="text-muted" style="font-size:.8em">${escHtml(n.notes)}</div>` : ''}
        </div>`).join('');
}

function renderFactions() {
    const el = document.getElementById('factions-list');
    const factions = draft.factions || [];
    if (!factions.length) { el.innerHTML = '<small class="text-muted">None specified</small>'; return; }
    el.innerHTML = factions.map(f => `
        <div class="mb-1 small">
            <span class="fw-semibold">${escHtml(f.name || '')}</span>
            ${f.disposition ? `<span class="badge ms-1 ${f.disposition==='hostile'?'bg-danger':f.disposition==='friendly'?'bg-success':'bg-secondary'}" style="font-size:.7em">${escHtml(f.disposition)}</span>` : ''}
            ${f.notes ? `<div class="text-muted" style="font-size:.8em">${escHtml(f.notes)}</div>` : ''}
        </div>`).join('');
}

// ---------------------------------------------------------------------------
// Room Editor
// ---------------------------------------------------------------------------

function openEditor(actIdx, sceneIdx, roomIdx) {
    currentRoomPath = { actIdx, sceneIdx, roomIdx };
    const room = draft.acts[actIdx].scenes[sceneIdx].rooms[roomIdx];

    document.getElementById('edit-key').value = room.key || '';
    document.getElementById('edit-title').value = room.title || '';
    document.getElementById('edit-read-aloud').value = room.read_aloud || '';
    document.getElementById('edit-gm-notes').value = room.gm_notes || '';

    renderCreatureEditor(room.creatures || []);
    renderLootEditor(room.loot || []);

    document.getElementById('room-editor').style.display = '';
    document.getElementById('edit-hint').style.display = 'none';

    // Highlight selected room
    document.querySelectorAll('.room-card').forEach(c => c.classList.remove('editing'));
    const allCards = document.querySelectorAll(`.room-card[data-act-idx="${actIdx}"][data-scene-idx="${sceneIdx}"][data-room-idx="${roomIdx}"]`);
    allCards.forEach(c => c.classList.add('editing'));
}

function closeEditor() {
    document.getElementById('room-editor').style.display = 'none';
    document.getElementById('edit-hint').style.display = '';
    document.querySelectorAll('.room-card').forEach(c => c.classList.remove('editing'));
    currentRoomPath = null;
}

function applyEdit() {
    if (!currentRoomPath) return;
    const { actIdx, sceneIdx, roomIdx } = currentRoomPath;
    const room = draft.acts[actIdx].scenes[sceneIdx].rooms[roomIdx];

    room.key = document.getElementById('edit-key').value.trim();
    room.title = document.getElementById('edit-title').value.trim();
    room.read_aloud = document.getElementById('edit-read-aloud').value.trim();
    room.gm_notes = document.getElementById('edit-gm-notes').value.trim();
    room.creatures = readCreatureEditor();
    room.loot = readLootEditor();

    // Re-render just the rooms section
    const container = document.getElementById(`rooms-${actIdx}-${sceneIdx}`);
    if (container) renderRooms(actIdx, sceneIdx, container);
    closeEditor();
}

// ---------------------------------------------------------------------------
// Creature editor (within the room editor panel)
// ---------------------------------------------------------------------------

function renderCreatureEditor(creatures) {
    const system = draft.system_hint || 'generic';
    const el = document.getElementById('edit-creatures');
    el.innerHTML = creatures.map((c, i) => {
        if (system === 'icrpg') {
            return `
                <div class="border border-secondary rounded p-2 mb-1 creature-row">
                    <input type="text" class="form-control form-control-sm bg-dark text-light border-secondary mb-1"
                           placeholder="Name" value="${escAttr(c.name || '')}">
                    <div class="row g-1">
                        <div class="col-4">
                            <input type="number" class="form-control form-control-sm bg-dark text-light border-secondary"
                                   placeholder="Hearts" value="${c.hearts || 1}" min="1">
                        </div>
                        <div class="col-8">
                            <select class="form-select form-select-sm bg-dark text-light border-secondary">
                                ${['BASIC','WEAPON','MAGIC','ULTIMATE'].map(e =>
                                    `<option ${c.effort_type===e?'selected':''}>${e}</option>`).join('')}
                            </select>
                        </div>
                    </div>
                    <input type="text" class="form-control form-control-sm bg-dark text-light border-secondary mt-1"
                           placeholder="Special move" value="${escAttr(c.special_move || '')}">
                    <button type="button" class="btn btn-sm btn-link text-danger p-0 mt-1" onclick="this.closest('.creature-row').remove()">Remove</button>
                </div>`;
        } else {
            return `
                <div class="border border-secondary rounded p-2 mb-1 creature-row">
                    <input type="text" class="form-control form-control-sm bg-dark text-light border-secondary mb-1"
                           placeholder="Name" value="${escAttr(c.name || '')}">
                    <div class="row g-1">
                        <div class="col-4"><input type="number" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="HP" value="${c.hp || ''}"></div>
                        <div class="col-4"><input type="number" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="AC" value="${c.ac || ''}"></div>
                        <div class="col-4"><input type="text" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="CR" value="${escAttr(c.cr || '')}"></div>
                    </div>
                    <input type="text" class="form-control form-control-sm bg-dark text-light border-secondary mt-1"
                           placeholder="Special move" value="${escAttr(c.special_move || '')}">
                    <button type="button" class="btn btn-sm btn-link text-danger p-0 mt-1" onclick="this.closest('.creature-row').remove()">Remove</button>
                </div>`;
        }
    }).join('');
}

function readCreatureEditor() {
    const system = draft.system_hint || 'generic';
    return Array.from(document.querySelectorAll('#edit-creatures .creature-row')).map(row => {
        const inputs = row.querySelectorAll('input, select');
        if (system === 'icrpg') {
            return { name: inputs[0].value, hearts: parseInt(inputs[1].value) || 1,
                     effort_type: inputs[2].value, special_move: inputs[3].value };
        } else {
            return { name: inputs[0].value, hp: parseInt(inputs[1].value) || null,
                     ac: parseInt(inputs[2].value) || null, cr: inputs[3].value,
                     special_move: inputs[4].value };
        }
    });
}

function addCreature() {
    const system = draft.system_hint || 'generic';
    const defaults = system === 'icrpg'
        ? { name: '', hearts: 1, effort_type: 'WEAPON', special_move: '' }
        : { name: '', hp: null, ac: null, cr: '', special_move: '' };
    const current = readCreatureEditor();
    current.push(defaults);
    renderCreatureEditor(current);
}

// ---------------------------------------------------------------------------
// Loot editor
// ---------------------------------------------------------------------------

function renderLootEditor(loot) {
    const el = document.getElementById('edit-loot');
    el.innerHTML = loot.map((l, i) => `
        <div class="d-flex gap-1 mb-1 loot-row">
            <input type="text" class="form-control form-control-sm bg-dark text-light border-secondary"
                   placeholder="Name" value="${escAttr(l.name || '')}">
            <input type="text" class="form-control form-control-sm bg-dark text-light border-secondary"
                   placeholder="Description" value="${escAttr(l.description || '')}">
            <button type="button" class="btn btn-sm btn-link text-danger p-0 flex-shrink-0" onclick="this.closest('.loot-row').remove()">✕</button>
        </div>`).join('');
}

function readLootEditor() {
    return Array.from(document.querySelectorAll('#edit-loot .loot-row')).map(row => {
        const inputs = row.querySelectorAll('input');
        return { name: inputs[0].value, description: inputs[1].value };
    }).filter(l => l.name);
}

function addLoot() {
    const current = readLootEditor();
    current.push({ name: '', description: '' });
    renderLootEditor(current);
}

// ---------------------------------------------------------------------------
// Add / Delete rooms and scenes
// ---------------------------------------------------------------------------

function addRoom(actIdx, sceneIdx) {
    const rooms = draft.acts[actIdx].scenes[sceneIdx].rooms;
    const nextKey = String.fromCharCode(65 + sceneIdx) + (rooms.length + 1);  // A1, A2...
    rooms.push({ key: nextKey, title: 'New Room', read_aloud: '', gm_notes: '', creatures: [], loot: [], hazards: [] });
    const container = document.getElementById(`rooms-${actIdx}-${sceneIdx}`);
    if (container) renderRooms(actIdx, sceneIdx, container);
    openEditor(actIdx, sceneIdx, rooms.length - 1);
}

function deleteRoom(event, actIdx, sceneIdx, roomIdx) {
    event.stopPropagation();
    if (!confirm('Delete this room?')) return;
    draft.acts[actIdx].scenes[sceneIdx].rooms.splice(roomIdx, 1);
    const container = document.getElementById(`rooms-${actIdx}-${sceneIdx}`);
    if (container) renderRooms(actIdx, sceneIdx, container);
    if (currentRoomPath?.actIdx === actIdx && currentRoomPath?.sceneIdx === sceneIdx) {
        closeEditor();
    }
}

function addScene(actIdx) {
    const scenes = draft.acts[actIdx].scenes;
    scenes.push({ title: 'New Scene', description: '', scene_type: '', rooms: [] });
    renderActs();
}

// ---------------------------------------------------------------------------
// Save to DB
// ---------------------------------------------------------------------------

async function saveDraft() {
    const btn = document.getElementById('save-btn');
    btn.disabled = true;
    document.getElementById('save-spinner').classList.remove('d-none');

    try {
        const resp = await fetch('/adventures/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
            },
            body: JSON.stringify(draft)
        });

        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Save failed');

        // Clear sessionStorage and redirect
        sessionStorage.removeItem('adventure_draft');
        window.location.href = data.redirect;

    } catch (err) {
        document.getElementById('save-spinner').classList.add('d-none');
        btn.disabled = false;
        alert('Save failed: ' + err.message);
    }
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function escHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escAttr(str) {
    return String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

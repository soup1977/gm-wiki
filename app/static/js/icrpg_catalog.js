/**
 * icrpg_catalog.js
 * AJAX CRUD handlers for the ICRPG Homebrew Catalog page.
 */
(function () {
    'use strict';

    var csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    var modalEl = document.getElementById('catalogFormModal');
    var modal = null;
    var currentEntity = null;   // 'world', 'lifeform', 'type', etc.
    var currentAction = null;   // 'create' or 'edit'
    var currentItemId = null;

    // Import state
    var importEntity = null;
    var importId = null;
    var importModalEl = document.getElementById('importConfirmModal');
    var importModal = null;

    // Type manage state (lazy-initialized)
    var typeManageEl = null;
    var typeManageModal = null;
    var currentManageTypeId = null;
    var manageAbilityData = {};

    // ── URL mapping ───────────────────────────────────────────────
    var URL_KEYS = {
        world: 'worlds', lifeform: 'life-forms', type: 'types',
        ability: 'abilities', loot: 'loot', spell: 'spells', path: 'paths'
    };

    // ── Helper: build a world <select> ────────────────────────────
    function worldSelect(selectedId) {
        var html = '<select id="cf-world-id" class="form-select form-select-sm bg-dark text-light border-secondary">';
        html += '<option value="">— None —</option>';
        for (var i = 0; i < CATALOG_WORLDS.length; i++) {
            var wid = CATALOG_WORLDS[i];
            var sel = wid === selectedId ? ' selected' : '';
            html += '<option value="' + wid + '"' + sel + '>' + (CATALOG_WORLD_NAMES[wid] || wid) + '</option>';
        }
        html += '</select>';
        return html;
    }

    // ── Helper: build a type <select> ─────────────────────────────
    function typeSelect(selectedId) {
        var html = '<select id="cf-type-id" class="form-select form-select-sm bg-dark text-light border-secondary">';
        html += '<option value="">— None —</option>';
        for (var i = 0; i < CATALOG_TYPES.length; i++) {
            var tid = CATALOG_TYPES[i];
            var sel = tid === selectedId ? ' selected' : '';
            html += '<option value="' + tid + '"' + sel + '>' + (CATALOG_TYPE_NAMES[tid] || tid) + '</option>';
        }
        html += '</select>';
        return html;
    }

    // ── Helper: form field shorthand ──────────────────────────────
    function field(id, label, value, type, placeholder) {
        type = type || 'text';
        value = value || '';
        var ph = placeholder ? ' placeholder="' + escapeHtml(placeholder) + '"' : '';
        if (type === 'textarea') {
            return '<div class="mb-2"><label class="form-label small">' + label + '</label>' +
                '<textarea id="cf-' + id + '" class="form-control form-control-sm bg-dark text-light border-secondary" rows="3"' + ph + '>' +
                escapeHtml(value) + '</textarea></div>';
        }
        return '<div class="mb-2"><label class="form-label small">' + label + '</label>' +
            '<input type="' + type + '" id="cf-' + id + '" class="form-control form-control-sm bg-dark text-light border-secondary" value="' +
            escapeHtml(value) + '"' + ph + '></div>';
    }

    function escapeHtml(s) {
        if (!s) return '';
        return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // ── Stat / bonus grid ─────────────────────────────────────────
    var STAT_COLS = [
        {key: 'STR', label: 'Strength'}, {key: 'DEX', label: 'Dexterity'},
        {key: 'CON', label: 'Constitution'}, {key: 'INT', label: 'Intelligence'},
        {key: 'WIS', label: 'Wisdom'}, {key: 'CHA', label: 'Charisma'}
    ];
    var EFFORT_COLS = [
        {key: 'BASIC_EFFORT', label: 'Basic (d4)'}, {key: 'WEAPON_EFFORT', label: 'Weapon (d6)'},
        {key: 'GUN_EFFORT', label: 'Gun (d8)'}, {key: 'MAGIC_EFFORT', label: 'Magic (d10)'},
        {key: 'ULTIMATE_EFFORT', label: 'Ultimate (d12)'}
    ];
    var OTHER_BONUS_COLS = [
        {key: 'DEFENSE', label: 'Defense'}, {key: 'HEARTS', label: 'Hearts'}
    ];
    var OTHER_EFFECT_COLS = [
        {key: 'DEFENSE', label: 'Defense'}, {key: 'HEARTS', label: 'Hearts'},
        {key: 'EQUIPPED_SLOTS', label: 'Equip Slots'}, {key: 'CARRIED_SLOTS', label: 'Carry Slots'}
    ];

    function numCell(key, label, val, prefix) {
        return '<div class="text-center px-1 mb-2">' +
            '<label class="d-block mb-1" style="font-size:0.68em;white-space:nowrap;">' + label + '</label>' +
            '<input type="number" id="cf-' + prefix + '-' + key + '" ' +
            'class="form-control form-control-sm bg-dark text-light border-secondary text-center" ' +
            'style="width:55px;margin:0 auto;" value="' + (val || 0) + '" min="-20" max="20">' +
            '</div>';
    }

    function statGrid(vals, prefix, otherCols, includeAbility) {
        vals = vals || {};
        var html = '';
        html += '<div class="form-label small text-uppercase text-secondary mb-1" style="font-size:0.7em;">Stats</div>';
        html += '<div class="d-flex flex-wrap mb-2">';
        STAT_COLS.forEach(function (k) { html += numCell(k.key, k.label, vals[k.key], prefix); });
        html += '</div>';
        html += '<div class="form-label small text-uppercase text-secondary mb-1" style="font-size:0.7em;">Effort Dice</div>';
        html += '<div class="d-flex flex-wrap mb-2">';
        EFFORT_COLS.forEach(function (k) { html += numCell(k.key, k.label, vals[k.key], prefix); });
        html += '</div>';
        html += '<div class="form-label small text-uppercase text-secondary mb-1" style="font-size:0.7em;">Other</div>';
        html += '<div class="d-flex flex-wrap mb-2">';
        otherCols.forEach(function (k) { html += numCell(k.key, k.label, vals[k.key], prefix); });
        html += '</div>';
        if (includeAbility) {
            html += '<div class="mb-1"><label class="form-label small">Innate Ability <span class="text-muted">(optional)</span></label>' +
                '<input type="text" id="cf-' + prefix + '-ABILITY" ' +
                'class="form-control form-control-sm bg-dark text-light border-secondary" ' +
                'value="' + escapeHtml(vals['ABILITY'] || '') + '" placeholder="e.g. Can breathe underwater"></div>';
        }
        return html;
    }

    function collectStatGrid(prefix, otherCols, includeAbility) {
        var result = {};
        var allCols = STAT_COLS.concat(EFFORT_COLS).concat(otherCols);
        allCols.forEach(function (k) {
            var el = document.getElementById('cf-' + prefix + '-' + k.key);
            if (!el) return;
            var val = parseInt(el.value);
            if (!isNaN(val) && val !== 0) result[k.key] = val;
        });
        if (includeAbility) {
            var el2 = document.getElementById('cf-' + prefix + '-ABILITY');
            if (el2 && el2.value.trim()) result['ABILITY'] = el2.value.trim();
        }
        return result;
    }

    // ── Tier editor ───────────────────────────────────────────────
    function tierItemRow(name, desc) {
        return '<div class="tier-item border border-secondary rounded p-2 mb-2">' +
            '<div class="d-flex gap-2 align-items-start">' +
            '<div class="flex-grow-1">' +
            '<input type="text" class="form-control form-control-sm bg-dark text-light border-secondary mb-1 tier-item-name" ' +
            'value="' + escapeHtml(name || '') + '" placeholder="Item name">' +
            '<textarea class="form-control form-control-sm bg-dark text-light border-secondary tier-item-desc" rows="2" ' +
            'placeholder="What this item does...">' + escapeHtml(desc || '') + '</textarea>' +
            '</div>' +
            '<button type="button" class="btn btn-sm btn-outline-danger flex-shrink-0" ' +
            'onclick="this.closest(\'.tier-item\').remove()"><i class="bi bi-x"></i></button>' +
            '</div></div>';
    }

    function tierEditor(tiers) {
        tiers = tiers || {};
        var html = '<div class="accordion" id="tier-accordion">';
        for (var t = 1; t <= 4; t++) {
            var items = tiers[String(t)] || [];
            var collapseId = 'tier-collapse-' + t;
            var isFirst = (t === 1);
            html += '<div class="accordion-item bg-dark border-secondary">';
            html += '<h2 class="accordion-header"><button class="accordion-button ' +
                (isFirst ? '' : 'collapsed') + ' bg-dark text-light py-2 small" ' +
                'type="button" data-bs-toggle="collapse" data-bs-target="#' + collapseId + '">' +
                'Tier ' + t + ' <span class="text-muted ms-2 fw-normal">(' + items.length + ' items)</span>' +
                '</button></h2>';
            html += '<div id="' + collapseId + '" class="accordion-collapse collapse' + (isFirst ? ' show' : '') + '">';
            html += '<div class="accordion-body p-2">';
            html += '<div id="tier-items-' + t + '">';
            items.forEach(function (item) { html += tierItemRow(item.name, item.description); });
            html += '</div>';
            html += '<button type="button" class="btn btn-sm btn-outline-secondary mt-1" ' +
                'onclick="addTierItem(' + t + ')"><i class="bi bi-plus me-1"></i>Add Item</button>';
            html += '</div></div></div>';
        }
        html += '</div>';
        return html;
    }

    window.addTierItem = function (tierNum) {
        var container = document.getElementById('tier-items-' + tierNum);
        if (!container) return;
        var tmp = document.createElement('div');
        tmp.innerHTML = tierItemRow('', '');
        container.appendChild(tmp.firstChild);
    };

    function collectTiers() {
        var result = {};
        for (var t = 1; t <= 4; t++) {
            var container = document.getElementById('tier-items-' + t);
            if (!container) continue;
            var items = [];
            container.querySelectorAll('.tier-item').forEach(function (row) {
                var nameEl = row.querySelector('.tier-item-name');
                var descEl = row.querySelector('.tier-item-desc');
                var name = nameEl ? nameEl.value.trim() : '';
                var desc = descEl ? descEl.value.trim() : '';
                if (name) items.push({name: name, description: desc});
            });
            if (items.length > 0) result[String(t)] = items;
        }
        return result;
    }

    // ── Build form HTML per entity type ───────────────────────────
    function buildForm(entity, data) {
        data = data || {};
        var html = '';
        switch (entity) {
            case 'world':
                html = field('name', 'Name', data.name) +
                    field('description', 'Description', data.description, 'textarea') +
                    field('basic-loot-count', 'Basic Loot Picks', data.basic_loot_count || 4, 'number',
                        'How many basic loot items characters choose (0 to skip)') +
                    field('include-world-loot', 'Also Include Loot From',
                        (data.include_world_loot || []).join(', '), 'text',
                        'Comma-separated world names, e.g. Alfheim, Warp Shell');
                break;
            case 'lifeform':
                html = field('name', 'Name', data.name) +
                    '<div class="mb-2"><label class="form-label small">World</label>' + worldSelect(data.world_id) + '</div>' +
                    field('description', 'Description', data.description, 'textarea') +
                    '<div class="mb-2"><label class="form-label small">Stat Bonuses</label>' +
                    statGrid(data.bonuses, 'bonus', OTHER_BONUS_COLS, true) + '</div>';
                break;
            case 'type':
                html = field('name', 'Name', data.name) +
                    '<div class="mb-2"><label class="form-label small">World</label>' + worldSelect(data.world_id) + '</div>' +
                    field('description', 'Description', data.description, 'textarea');
                break;
            case 'ability':
                html = field('name', 'Name', data.name) +
                    '<div class="mb-2"><label class="form-label small">Type (class)</label>' + typeSelect(data.type_id) + '</div>' +
                    '<div class="mb-2"><label class="form-label small">Kind</label>' +
                    '<select id="cf-ability-kind" class="form-select form-select-sm bg-dark text-light border-secondary">' +
                    '<option value="starting"' + (data.ability_kind === 'starting' ? ' selected' : '') + '>Starting</option>' +
                    '<option value="milestone"' + (data.ability_kind === 'milestone' ? ' selected' : '') + '>Milestone</option>' +
                    '<option value="mastery"' + (data.ability_kind === 'mastery' ? ' selected' : '') + '>Mastery</option>' +
                    '</select></div>' +
                    field('description', 'Description', data.description, 'textarea');
                break;
            case 'loot':
                html = field('name', 'Name', data.name) +
                    '<div class="mb-2"><label class="form-label small">World (optional)</label>' + worldSelect(data.world_id) + '</div>' +
                    field('loot-type', 'Loot Type', data.loot_type, 'text', 'Armor, Weapon, Shield, Gear...') +
                    field('description', 'Description', data.description, 'textarea') +
                    '<div class="mb-2"><label class="form-label small">Effects</label>' +
                    statGrid(data.effects, 'effect', OTHER_EFFECT_COLS, false) + '</div>' +
                    field('slot-cost', 'Slot Cost', data.slot_cost || 1, 'number') +
                    field('coin-cost', 'Coin Cost', data.coin_cost || 0, 'number') +
                    '<div class="mb-2 form-check">' +
                    '<input type="checkbox" class="form-check-input" id="cf-is-starter"' +
                    (data.is_starter ? ' checked' : '') + '>' +
                    '<label class="form-check-label small" for="cf-is-starter">' +
                    'Basic/Starter Loot (available during character creation)</label></div>';
                break;
            case 'spell':
                html = field('name', 'Name', data.name) +
                    field('spell-type', 'Spell Type', data.spell_type, 'text', 'Arcane, Holy, Infernal') +
                    field('casting-stat', 'Casting Stat', data.casting_stat, 'text', 'INT (Arcane) or WIS (Holy/Infernal)') +
                    field('level', 'Level', data.level || 1, 'number') +
                    field('target', 'Target', data.target, 'text', 'Single, Area, Self...') +
                    field('duration', 'Duration', data.duration, 'text', 'Instant, 1D4 Rounds, Scene...') +
                    field('description', 'Description', data.description, 'textarea');
                break;
            case 'path':
                html = field('name', 'Name', data.name) +
                    field('description', 'Description', data.description, 'textarea') +
                    '<div class="mb-2"><label class="form-label small mb-1">Tiers</label>' +
                    tierEditor(data.tiers) + '</div>';
                break;
        }
        return html;
    }

    // ── Collect form data per entity type ─────────────────────────
    function collectData(entity) {
        var data = {};
        var v = function (id) { var el = document.getElementById('cf-' + id); return el ? el.value.trim() : ''; };
        switch (entity) {
            case 'world':
                var inclRaw = v('include-world-loot');
                var inclArr = inclRaw ? inclRaw.split(',').map(function(s){ return s.trim(); }).filter(Boolean) : [];
                data = { name: v('name'), description: v('description'),
                    basic_loot_count: parseInt(v('basic-loot-count')) || 4,
                    include_world_loot: inclArr.length > 0 ? inclArr : null };
                break;
            case 'lifeform':
                var bonuses = collectStatGrid('bonus', OTHER_BONUS_COLS, true);
                data = { name: v('name'), description: v('description'), bonuses: bonuses };
                var ws = document.getElementById('cf-world-id');
                data.world_id = ws && ws.value ? parseInt(ws.value) : null;
                break;
            case 'type':
                data = { name: v('name'), description: v('description') };
                var ws2 = document.getElementById('cf-world-id');
                data.world_id = ws2 && ws2.value ? parseInt(ws2.value) : null;
                break;
            case 'ability':
                data = { name: v('name'), description: v('description') };
                var ts = document.getElementById('cf-type-id');
                data.type_id = ts && ts.value ? parseInt(ts.value) : null;
                var ks = document.getElementById('cf-ability-kind');
                data.ability_kind = ks ? ks.value : 'starting';
                break;
            case 'loot':
                var effects = collectStatGrid('effect', OTHER_EFFECT_COLS, false);
                var isStarter = document.getElementById('cf-is-starter');
                data = { name: v('name'), description: v('description'),
                    loot_type: v('loot-type'), effects: effects,
                    slot_cost: parseInt(v('slot-cost')) || 1,
                    coin_cost: parseInt(v('coin-cost')) || 0,
                    is_starter: isStarter ? isStarter.checked : false };
                var ws3 = document.getElementById('cf-world-id');
                data.world_id = ws3 && ws3.value ? parseInt(ws3.value) : null;
                break;
            case 'spell':
                data = { name: v('name'), description: v('description'),
                    spell_type: v('spell-type'), casting_stat: v('casting-stat'),
                    level: parseInt(v('level')) || 1,
                    target: v('target'), duration: v('duration') };
                break;
            case 'path':
                data = { name: v('name'), description: v('description'), tiers: collectTiers() };
                break;
        }
        if (!data.name) { alert('Name is required.'); return null; }
        return data;
    }

    // ── Open modal ────────────────────────────────────────────────
    window.catalogModal = function (entity, action, itemId, data) {
        currentEntity = entity;
        currentAction = action;
        currentItemId = itemId || null;
        var title = (action === 'edit' ? 'Edit ' : 'New ') + entity.charAt(0).toUpperCase() + entity.slice(1);
        document.getElementById('catalogModalTitle').textContent = title;
        document.getElementById('catalogModalBody').innerHTML = buildForm(entity, data);
        if (!modal) modal = new bootstrap.Modal(modalEl);
        modal.show();
    };

    // ── Delegated click listener for edit buttons (data-* attrs) ──
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.catalog-edit-btn');
        if (!btn) return;
        var data = JSON.parse(btn.dataset.payload);
        catalogModal(btn.dataset.entity, 'edit', parseInt(btn.dataset.id), data);
    });

    // ── Delete ────────────────────────────────────────────────────
    window.catalogDelete = function (urlKey, itemId, name) {
        if (!confirm('Delete "' + name + '"? This cannot be undone.')) return;
        fetch('/icrpg-catalog/' + urlKey + '/' + itemId + '/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({})
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.error) { alert(data.error); return; }
            window.location.reload();
        })
        .catch(function (err) { console.error(err); });
    };

    // ── Save button handler ───────────────────────────────────────
    document.getElementById('catalogModalSave').addEventListener('click', function () {
        var data = collectData(currentEntity);
        if (!data) return;
        var urlKey = URL_KEYS[currentEntity];
        var url = '/icrpg-catalog/' + urlKey + '/';
        if (currentAction === 'edit') {
            url += currentItemId + '/edit';
        } else {
            url += 'create';
        }
        fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify(data)
        })
        .then(function (r) { return r.json(); })
        .then(function (result) {
            if (result.error) { alert(result.error); return; }
            if (modal) modal.hide();
            window.location.reload();
        })
        .catch(function (err) { console.error(err); });
    });

    // ── Import to Homebrew ────────────────────────────────────────
    window.importBuiltin = function (entity, id, name) {
        importEntity = entity;
        importId = id;

        document.getElementById('import-entity-name').textContent = name;
        var pickerDiv = document.getElementById('import-picker');
        var confirmBtn = document.getElementById('import-confirm-btn');
        pickerDiv.innerHTML = '';
        confirmBtn.style.display = '';

        if (entity === 'lifeform' || entity === 'type') {
            if (!IMPORT_HOMEBREW_WORLDS || IMPORT_HOMEBREW_WORLDS.length === 0) {
                pickerDiv.innerHTML = '<div class="alert alert-warning small mb-0">You need at least one homebrew world first. Create one in the Worlds tab.</div>';
                confirmBtn.style.display = 'none';
            } else {
                var sel = '<div class="mb-0"><label class="form-label small">Target World</label>' +
                    '<select id="import-world-select" class="form-select form-select-sm bg-dark text-light border-secondary">';
                IMPORT_HOMEBREW_WORLDS.forEach(function (w) {
                    sel += '<option value="' + w.id + '">' + escapeHtml(w.name) + '</option>';
                });
                sel += '</select></div>';
                pickerDiv.innerHTML = sel;
            }
        } else if (entity === 'ability') {
            if (!IMPORT_HOMEBREW_TYPES || IMPORT_HOMEBREW_TYPES.length === 0) {
                pickerDiv.innerHTML = '<div class="alert alert-warning small mb-0">You need at least one homebrew type first. Create one in the Types tab.</div>';
                confirmBtn.style.display = 'none';
            } else {
                var sel2 = '<div class="mb-0"><label class="form-label small">Target Type (class)</label>' +
                    '<select id="import-type-select" class="form-select form-select-sm bg-dark text-light border-secondary">';
                IMPORT_HOMEBREW_TYPES.forEach(function (t) {
                    sel2 += '<option value="' + t.id + '">' + escapeHtml(t.name) + '</option>';
                });
                sel2 += '</select></div>';
                pickerDiv.innerHTML = sel2;
            }
        }

        if (!importModal) importModal = new bootstrap.Modal(importModalEl);
        importModal.show();
    };

    document.getElementById('import-confirm-btn').addEventListener('click', function () {
        var body = {};
        var worldSel = document.getElementById('import-world-select');
        var typeSel = document.getElementById('import-type-select');
        if (worldSel && worldSel.value) body.target_world_id = parseInt(worldSel.value);
        if (typeSel && typeSel.value) body.target_type_id = parseInt(typeSel.value);

        var urlKey = URL_KEYS[importEntity];
        fetch('/icrpg-catalog/' + urlKey + '/' + importId + '/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify(body)
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.error) { alert(data.error); return; }
            if (importModal) importModal.hide();
            window.location.reload();
        })
        .catch(function (err) { console.error(err); });
    });

    // ── Type Manage Modal ─────────────────────────────────────────
    window.openTypeManage = function (typeId, typeName) {
        currentManageTypeId = typeId;
        if (!typeManageEl) typeManageEl = document.getElementById('typeManageModal');
        document.getElementById('typeManageTitle').textContent = typeName;
        loadTypeManage(typeId);
        if (!typeManageModal && typeManageEl) typeManageModal = new bootstrap.Modal(typeManageEl);
        if (typeManageModal) typeManageModal.show();
    };

    function loadTypeManage(typeId) {
        var body = document.getElementById('typeManageBody');
        body.innerHTML = '<p class="text-muted small py-3 text-center">Loading...</p>';
        fetch('/icrpg-catalog/types/' + typeId + '/manage', {
            headers: { 'X-CSRFToken': csrfToken }
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            manageAbilityData = {};
            (data.abilities || []).forEach(function (ab) { manageAbilityData[ab.id] = ab; });
            body.innerHTML = renderTypeManage(data, typeId);
        })
        .catch(function (err) { console.error(err); });
    }

    function renderTypeManage(data, typeId) {
        var html = '';

        // Abilities section
        html += '<h6 class="text-uppercase text-muted mb-2" style="font-size:0.7em;letter-spacing:.05em;">Abilities</h6>';
        if (!data.abilities || data.abilities.length === 0) {
            html += '<p class="text-muted small mb-2">No abilities yet.</p>';
        } else {
            html += '<table class="table table-dark table-sm mb-2"><tbody>';
            data.abilities.forEach(function (ab) {
                var kindColor = ab.ability_kind === 'starting' ? 'info' :
                    (ab.ability_kind === 'milestone' ? 'warning' : 'danger');
                html += '<tr>' +
                    '<td class="fw-semibold small">' + escapeHtml(ab.name) + '</td>' +
                    '<td><span class="badge bg-' + kindColor + ' small">' + ab.ability_kind + '</span></td>' +
                    '<td class="text-muted small">' +
                    escapeHtml((ab.description || '').substring(0, 50)) +
                    ((ab.description || '').length > 50 ? '...' : '') + '</td>' +
                    '<td class="text-end text-nowrap">' +
                    '<button class="btn btn-sm btn-outline-secondary me-1 manage-edit-ability" data-id="' + ab.id + '">' +
                    '<i class="bi bi-pencil"></i></button>' +
                    '<button class="btn btn-sm btn-outline-danger manage-delete-ability" data-id="' + ab.id + '">' +
                    '<i class="bi bi-trash"></i></button>' +
                    '</td></tr>';
            });
            html += '</tbody></table>';
        }
        html += '<button class="btn btn-sm btn-outline-success mb-3 manage-add-ability" data-type-id="' + typeId + '">' +
            '<i class="bi bi-plus-circle me-1"></i>Add Ability</button>'
            + ' <button class="btn btn-sm btn-outline-info mb-3 manage-ai-generate" data-type-id="' + typeId + '">'
            + '<i class="bi bi-stars me-1"></i>AI Ideas</button>';

        // Starting Loot section
        html += '<hr class="border-secondary">';
        html += '<h6 class="text-uppercase text-muted mb-1" style="font-size:0.7em;letter-spacing:.05em;">Starting Loot Options</h6>';
        html += '<p class="text-muted small mb-2">Players choose one of these when creating a character of this type.</p>';
        if (!data.starting_loot || data.starting_loot.length === 0) {
            html += '<p class="text-muted small mb-2">No starting loot yet.</p>';
        } else {
            html += '<ul class="list-group list-group-flush mb-2">';
            data.starting_loot.forEach(function (sl) {
                html += '<li class="list-group-item bg-dark border-secondary d-flex justify-content-between align-items-center py-1">' +
                    '<span class="small">' + escapeHtml(sl.name) + '</span>' +
                    '<button class="btn btn-sm btn-outline-danger py-0 manage-remove-sl" ' +
                    'data-sl-id="' + sl.id + '" data-type-id="' + typeId + '">' +
                    '<i class="bi bi-x"></i></button></li>';
            });
            html += '</ul>';
        }
        // Add loot/spell picker
        html += '<div class="d-flex gap-2 align-items-end mt-1">';
        html += '<div class="flex-grow-1"><label class="form-label small mb-1">Add Item</label>';
        html += '<select id="sl-add-select" class="form-select form-select-sm bg-dark text-light border-secondary">';
        html += '<option value="">— Pick loot or spell —</option>';
        if (data.all_loot && data.all_loot.length > 0) {
            html += '<optgroup label="Loot">';
            data.all_loot.forEach(function (ld) {
                html += '<option value="loot-' + ld.id + '">' + escapeHtml(ld.name) + '</option>';
            });
            html += '</optgroup>';
        }
        if (data.all_spells && data.all_spells.length > 0) {
            html += '<optgroup label="Spells">';
            data.all_spells.forEach(function (sp) {
                html += '<option value="spell-' + sp.id + '">' + escapeHtml(sp.name) + '</option>';
            });
            html += '</optgroup>';
        }
        html += '</select></div>';
        html += '<button class="btn btn-sm btn-outline-primary manage-add-sl" data-type-id="' + typeId + '">' +
            '<i class="bi bi-plus me-1"></i>Add</button>';
        html += '</div>';

        // AI Generate section
        html += '<hr class="border-secondary">';
        html += '<div id="manage-ai-section">';
        html += '<div class="d-flex align-items-center gap-2 mb-2">';
        html += '<span class="text-muted small">Generate AI ideas for this type:</span>';
        html += '<input type="text" id="manage-ai-concept" class="form-control form-control-sm bg-dark text-light border-secondary" '
             + 'style="max-width:220px;" placeholder="Optional concept hint">';
        html += '<button class="btn btn-sm btn-info manage-ai-run" data-type-id="' + typeId + '">'
             + '<i class="bi bi-stars me-1"></i>Generate</button>';
        html += '</div>';
        html += '<div id="manage-ai-spinner" style="display:none;" class="text-muted small">'
             + '<span class="spinner-border spinner-border-sm me-1"></span>Generating…</div>';
        html += '<div id="manage-ai-results"></div>';
        html += '</div>';

        return html;
    }

    // Delegated listeners for type manage modal
    document.addEventListener('click', function (e) {
        // Edit ability
        var editBtn = e.target.closest('.manage-edit-ability');
        if (editBtn) {
            var abilityId = parseInt(editBtn.dataset.id);
            var ab = manageAbilityData[abilityId];
            if (typeManageModal) typeManageModal.hide();
            catalogModal('ability', 'edit', abilityId, ab);
            return;
        }
        // Delete ability
        var delBtn = e.target.closest('.manage-delete-ability');
        if (delBtn) {
            if (!confirm('Delete this ability?')) return;
            var abilityId2 = parseInt(delBtn.dataset.id);
            fetch('/icrpg-catalog/abilities/' + abilityId2 + '/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({})
            })
            .then(function (r) { return r.json(); })
            .then(function (result) {
                if (result.error) { alert(result.error); return; }
                loadTypeManage(currentManageTypeId);
            });
            return;
        }
        // Add ability button
        var addAbBtn = e.target.closest('.manage-add-ability');
        if (addAbBtn) {
            var preTypeId = parseInt(addAbBtn.dataset.typeId);
            if (typeManageModal) typeManageModal.hide();
            catalogModal('ability', 'create', null, {type_id: preTypeId});
            return;
        }
        // Remove starting loot
        var removeSlBtn = e.target.closest('.manage-remove-sl');
        if (removeSlBtn) {
            var slId = parseInt(removeSlBtn.dataset.slId);
            var slTypeId = parseInt(removeSlBtn.dataset.typeId);
            fetch('/icrpg-catalog/types/' + slTypeId + '/starting-loot/' + slId + '/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({})
            })
            .then(function (r) { return r.json(); })
            .then(function (result) {
                if (result.error) { alert(result.error); return; }
                loadTypeManage(currentManageTypeId);
            });
            return;
        }
        // Add starting loot
        var addSlBtn = e.target.closest('.manage-add-sl');
        if (addSlBtn) {
            var sel = document.getElementById('sl-add-select');
            if (!sel || !sel.value) { alert('Pick an item first.'); return; }
            var parts = sel.value.split('-');
            var body = {};
            if (parts[0] === 'loot') body.loot_def_id = parseInt(parts[1]);
            else body.spell_id = parseInt(parts[1]);
            var addTypeId = parseInt(addSlBtn.dataset.typeId);
            fetch('/icrpg-catalog/types/' + addTypeId + '/starting-loot/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify(body)
            })
            .then(function (r) { return r.json(); })
            .then(function (result) {
                if (result.error) { alert(result.error); return; }
                loadTypeManage(currentManageTypeId);
            });
            return;
        }
        // AI Ideas toggle (just scrolls to the generate section at bottom)
        var aiGenToggle = e.target.closest('.manage-ai-generate');
        if (aiGenToggle) {
            var sec = document.getElementById('manage-ai-section');
            if (sec) sec.scrollIntoView({behavior: 'smooth', block: 'nearest'});
            var inp = document.getElementById('manage-ai-concept');
            if (inp) inp.focus();
            return;
        }

        // AI Generate run
        var aiRunBtn = e.target.closest('.manage-ai-run');
        if (!aiRunBtn) return;
        var aiTypeId = aiRunBtn.dataset.typeId;
        var conceptInput = document.getElementById('manage-ai-concept');
        var concept = conceptInput ? conceptInput.value.trim() : '';
        var spinner = document.getElementById('manage-ai-spinner');
        var results = document.getElementById('manage-ai-results');
        if (spinner) spinner.style.display = 'block';
        if (results) results.innerHTML = '';
        aiRunBtn.disabled = true;

        // Get type name/description from current manage data
        var manageTitle = document.getElementById('typeManageTitle');
        var typeName = manageTitle ? manageTitle.textContent : '';

        fetch('/api/ai/generate-type-content', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({type_name: typeName, type_description: '', concept: concept})
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (spinner) spinner.style.display = 'none';
            aiRunBtn.disabled = false;
            if (data.error) {
                if (results) results.innerHTML = '<div class="alert alert-danger small mt-2">' + data.error + '</div>';
                return;
            }
            var html = '';
            // Abilities suggestions
            var abilities = data.abilities || [];
            if (abilities.length) {
                html += '<div class="mt-2"><strong class="small text-info">Ability Ideas</strong></div>';
                abilities.forEach(function (ab, i) {
                    var kindColor = ab.ability_kind === 'starting' ? 'info' : ab.ability_kind === 'milestone' ? 'warning' : 'danger';
                    html += '<div class="card bg-secondary border-0 mb-1 p-2 d-flex flex-row align-items-start gap-2">';
                    html += '<div class="flex-grow-1">';
                    html += '<span class="badge bg-' + kindColor + ' me-1">' + (ab.ability_kind || '') + '</span>';
                    html += '<strong class="small">' + escapeHtml(ab.name || '') + '</strong> ';
                    html += '<span class="text-muted small">' + escapeHtml((ab.description || '').substring(0, 80)) + '</span>';
                    html += '</div>';
                    html += '<button class="btn btn-sm btn-success py-0 flex-shrink-0 manage-ai-add-ability" '
                         + 'data-type-id="' + aiTypeId + '" '
                         + 'data-name="' + escapeHtml(ab.name || '') + '" '
                         + 'data-desc="' + escapeHtml(ab.description || '') + '" '
                         + 'data-kind="' + (ab.ability_kind || 'starting') + '">'
                         + '<i class="bi bi-plus"></i></button>';
                    html += '</div>';
                });
            }
            // Starting loot suggestions
            var loot = data.starting_loot || [];
            if (loot.length) {
                html += '<div class="mt-2"><strong class="small text-warning">Starting Loot Ideas</strong></div>';
                loot.forEach(function (ld) {
                    html += '<div class="card bg-secondary border-0 mb-1 p-2 d-flex flex-row align-items-start gap-2">';
                    html += '<div class="flex-grow-1">';
                    html += '<span class="badge bg-secondary border border-info me-1">' + (ld.loot_type || '') + '</span>';
                    html += '<strong class="small">' + escapeHtml(ld.name || '') + '</strong> ';
                    html += '<span class="text-muted small">' + escapeHtml((ld.description || '').substring(0, 80)) + '</span>';
                    html += '</div>';
                    html += '<button class="btn btn-sm btn-success py-0 flex-shrink-0 manage-ai-add-loot" '
                         + 'data-type-id="' + aiTypeId + '" '
                         + 'data-name="' + escapeHtml(ld.name || '') + '" '
                         + 'data-desc="' + escapeHtml(ld.description || '') + '" '
                         + 'data-loot-type="' + (ld.loot_type || 'Item') + '" '
                         + 'data-effects=\'' + JSON.stringify(ld.effects || {}) + '\' '
                         + 'data-slot-cost="' + (ld.slot_cost || 1) + '">'
                         + '<i class="bi bi-plus"></i></button>';
                    html += '</div>';
                });
            }
            if (results) results.innerHTML = html;
        })
        .catch(function () {
            if (spinner) spinner.style.display = 'none';
            aiRunBtn.disabled = false;
            if (results) results.innerHTML = '<div class="alert alert-danger small mt-2">Request failed.</div>';
        });
    });

    // Delegated listener for manage-ai-add-ability and manage-ai-add-loot
    document.addEventListener('click', function (e) {
        var addAbBtn = e.target.closest('.manage-ai-add-ability');
        if (addAbBtn) {
            var payload = {
                name: addAbBtn.dataset.name,
                description: addAbBtn.dataset.desc,
                ability_kind: addAbBtn.dataset.kind,
                type_id: parseInt(addAbBtn.dataset.typeId)
            };
            fetch('/icrpg-catalog/abilities/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                body: JSON.stringify(payload)
            })
            .then(function (r) { return r.json(); })
            .then(function (result) {
                if (result.error) { alert(result.error); return; }
                addAbBtn.disabled = true;
                addAbBtn.innerHTML = '<i class="bi bi-check"></i>';
                addAbBtn.classList.replace('btn-success', 'btn-secondary');
                loadTypeManage(currentManageTypeId);
            });
            return;
        }

        var addLdBtn = e.target.closest('.manage-ai-add-loot');
        if (addLdBtn) {
            var typeId = addLdBtn.dataset.typeId;
            var lootPayload = {
                name: addLdBtn.dataset.name,
                description: addLdBtn.dataset.desc,
                loot_type: addLdBtn.dataset.lootType,
                slot_cost: parseInt(addLdBtn.dataset.slotCost) || 1,
                effects: JSON.parse(addLdBtn.dataset.effects || '{}')
            };
            // First create the loot entry, then link it as starting loot
            fetch('/icrpg-catalog/loot/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                body: JSON.stringify(lootPayload)
            })
            .then(function (r) { return r.json(); })
            .then(function (result) {
                if (result.error) { alert(result.error); return; }
                var lootId = result.id;
                return fetch('/icrpg-catalog/types/' + typeId + '/starting-loot/add', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                    body: JSON.stringify({loot_def_id: lootId})
                });
            })
            .then(function (r) { return r ? r.json() : null; })
            .then(function (result) {
                if (!result) return;
                if (result.error) { alert(result.error); return; }
                addLdBtn.disabled = true;
                addLdBtn.innerHTML = '<i class="bi bi-check"></i>';
                addLdBtn.classList.replace('btn-success', 'btn-secondary');
                loadTypeManage(currentManageTypeId);
            })
            .catch(function () { alert('Request failed.'); });
        }
    });

    // ── ICRPG AI Generator ────────────────────────────────────────

    var icrpgAIModalEl = null;
    var icrpgAIModal   = null;
    var icrpgAIMode    = 'generate'; // 'generate' or 'retheme'
    var icrpgAIEntity  = null;
    var icrpgAIRethemeId = null;
    var icrpgAIRethemeData = null;

    var ICRPG_URL_KEYS = {
        lifeform: 'life-forms', type: 'types', ability: 'abilities',
        loot: 'loot', spell: 'spells', path: 'paths'
    };
    var ICRPG_EDIT_ROUTES = {
        lifeform: 'life-forms', type: 'types', ability: 'abilities',
        loot: 'loot', spell: 'spells', path: 'paths'
    };

    window.openIcrpgAI = function (entityType, entityLabel) {
        icrpgAIMode   = 'generate';
        icrpgAIEntity = entityType;
        _initIcrpgModal();
        document.getElementById('icrpgAIModalTitle').textContent = 'AI Homebrew Ideas — ' + entityLabel;
        document.getElementById('icrpgAIControls').style.display = 'block';
        document.getElementById('icrpgAIThemeRow').style.display = 'none';
        document.getElementById('icrpgAIGenerateBtn').style.display = '';
        document.getElementById('icrpgAIConcept').value = '';
        document.getElementById('icrpgAIResults').innerHTML = '';
        document.getElementById('icrpgAISpinner').style.display = 'none';
        icrpgAIModal.show();
    };

    window.openIcrpgRetheme = function (entityType, entityId, payloadJson) {
        icrpgAIMode       = 'retheme';
        icrpgAIEntity     = entityType;
        icrpgAIRethemeId  = entityId;
        try { icrpgAIRethemeData = JSON.parse(payloadJson); }
        catch (e) { icrpgAIRethemeData = {}; }
        _initIcrpgModal();
        document.getElementById('icrpgAIModalTitle').textContent = 'Retheme: ' + (icrpgAIRethemeData.name || entityType);
        document.getElementById('icrpgAIControls').style.display = 'block';
        document.getElementById('icrpgAIThemeRow').style.display = 'block';
        document.getElementById('icrpgAIGenerateBtn').style.display = 'none';
        document.getElementById('icrpgAITheme').value = '';
        document.getElementById('icrpgAIResults').innerHTML = '';
        document.getElementById('icrpgAISpinner').style.display = 'none';
        icrpgAIModal.show();
    };

    function _initIcrpgModal() {
        if (!icrpgAIModalEl) icrpgAIModalEl = document.getElementById('icrpgAIModal');
        if (!icrpgAIModal && icrpgAIModalEl) icrpgAIModal = new bootstrap.Modal(icrpgAIModalEl);
    }

    window.runIcrpgGenerate = function () {
        var concept = document.getElementById('icrpgAIConcept').value.trim();
        var count   = parseInt(document.getElementById('icrpgAICount').value, 10) || 3;
        _showIcrpgSpinner(true);
        fetch('/api/ai/generate-icrpg', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({entity_type: icrpgAIEntity, concept: concept, count: count})
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            _showIcrpgSpinner(false);
            if (data.error) { _icrpgError(data.error); return; }
            _renderIcrpgSuggestions(data.suggestions || [], false);
        })
        .catch(function () { _showIcrpgSpinner(false); _icrpgError('Request failed.'); });
    };

    window.runIcrpgRetheme = function () {
        var theme = document.getElementById('icrpgAITheme').value.trim();
        if (!theme) { alert('Please enter a theme.'); return; }
        _showIcrpgSpinner(true);
        fetch('/api/ai/retheme-icrpg', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({entity_type: icrpgAIEntity, existing_data: icrpgAIRethemeData, theme: theme})
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            _showIcrpgSpinner(false);
            if (data.error) { _icrpgError(data.error); return; }
            var suggestion = data.suggestion || {};
            _renderIcrpgSuggestions([suggestion], true);
        })
        .catch(function () { _showIcrpgSpinner(false); _icrpgError('Request failed.'); });
    };

    function _showIcrpgSpinner(show) {
        document.getElementById('icrpgAISpinner').style.display = show ? 'block' : 'none';
        document.getElementById('icrpgAIResults').innerHTML = '';
        var genBtn = document.getElementById('icrpgAIGenerateBtn');
        var rethBtn = document.getElementById('icrpgAIRethemeBtn');
        if (genBtn) genBtn.disabled = show;
        if (rethBtn) rethBtn.disabled = show;
    }

    function _icrpgError(msg) {
        document.getElementById('icrpgAIResults').innerHTML =
            '<div class="alert alert-danger small">' + msg + '</div>';
    }

    function _renderIcrpgSuggestions(suggestions, isRetheme) {
        var container = document.getElementById('icrpgAIResults');
        if (!suggestions || !suggestions.length) {
            container.innerHTML = '<p class="text-muted small">No suggestions returned.</p>';
            return;
        }
        var html = '';
        suggestions.forEach(function (s, idx) {
            html += '<div class="card bg-secondary border-0 mb-3" id="icrpg-card-' + idx + '">';
            html += '<div class="card-body p-3">';
            html += '<div class="d-flex justify-content-between align-items-start mb-2">';
            html += '<strong class="text-light">' + (s.name || '(no name)') + '</strong>';
            html += '<div class="d-flex gap-1">';
            if (isRetheme) {
                html += '<button class="btn btn-sm btn-success py-0" onclick="addIcrpgEntry(' + idx + ', false)">'
                      + '<i class="bi bi-plus-circle me-1"></i>Save as New</button>';
                html += '<button class="btn btn-sm btn-warning py-0" onclick="addIcrpgEntry(' + idx + ', true)">'
                      + '<i class="bi bi-arrow-repeat me-1"></i>Overwrite</button>';
            } else {
                html += '<button class="btn btn-sm btn-success py-0" onclick="addIcrpgEntry(' + idx + ', false)">'
                      + '<i class="bi bi-plus-circle me-1"></i>Add to Catalog</button>';
            }
            html += '</div></div>';
            // Description
            if (s.description) {
                html += '<p class="small text-light mb-2">' + s.description + '</p>';
            }
            // Entity-specific detail display
            html += _icrpgSuggestionDetails(s, icrpgAIEntity);
            html += '</div></div>';
        });
        container.innerHTML = html;
        // Store suggestions for later retrieval
        container._suggestions = suggestions;
    }

    function _icrpgSuggestionDetails(s, entityType) {
        var parts = [];
        if (entityType === 'lifeform' && s.bonuses && Object.keys(s.bonuses).length) {
            var bonusLabels = {STR:'STR',DEX:'DEX',CON:'CON',INT:'INT',WIS:'WIS',CHA:'CHA',
                BASIC_EFFORT:'Basic Effort',WEAPON_EFFORT:'Weapon Effort',GUN_EFFORT:'Gun Effort',
                MAGIC_EFFORT:'Magic Effort',ULTIMATE_EFFORT:'Ultimate Effort',
                HEARTS:'Hearts',DEFENSE:'Defense',ABILITY:'Innate Ability'};
            var items = [];
            var abilityText = null;
            Object.keys(s.bonuses).forEach(function (k) {
                if (k === 'ABILITY') { abilityText = s.bonuses[k]; return; }
                var label = bonusLabels[k] || k;
                var val = s.bonuses[k];
                items.push('<span class="badge bg-dark border border-secondary me-1">' + label + ': '
                    + (typeof val === 'number' && val > 0 ? '+' : '') + val + '</span>');
            });
            if (abilityText) parts.push('<div class="text-muted small fst-italic mt-1"><strong>Innate Ability:</strong> ' + escapeHtml(abilityText) + '</div>');
            if (items.length) parts.push('<div class="mt-1">' + items.join('') + '</div>');
        }
        if (entityType === 'loot') {
            var meta = [];
            if (s.loot_type) meta.push('<span class="badge bg-secondary border border-info">' + s.loot_type + '</span>');
            if (s.slot_cost) meta.push('<span class="text-muted small">Slots: ' + s.slot_cost + '</span>');
            if (s.coin_cost) meta.push('<span class="text-muted small">Cost: ' + s.coin_cost + 'gp</span>');
            if (meta.length) parts.push('<div class="mb-1">' + meta.join(' ') + '</div>');
            if (s.effects && Object.keys(s.effects).length) {
                var efxLabels = {STR:'STR',DEX:'DEX',CON:'CON',INT:'INT',WIS:'WIS',CHA:'CHA',
                    BASIC_EFFORT:'Basic Effort',WEAPON_EFFORT:'Weapon Effort',GUN_EFFORT:'Gun Effort',
                    MAGIC_EFFORT:'Magic Effort',ULTIMATE_EFFORT:'Ultimate Effort',
                    HEARTS:'Hearts',DEFENSE:'Defense',EQUIPPED_SLOTS:'Equip Slots',CARRIED_SLOTS:'Carry Slots'};
                var efxItems = [];
                Object.keys(s.effects).forEach(function (k) {
                    var val = s.effects[k];
                    efxItems.push('<span class="badge bg-dark border border-warning me-1">' + (efxLabels[k]||k) + ': '
                        + (typeof val === 'number' && val > 0 ? '+' : '') + val + '</span>');
                });
                if (efxItems.length) parts.push('<div>' + efxItems.join('') + '</div>');
            }
        }
        if (entityType === 'spell') {
            var smeta = [];
            if (s.spell_type) smeta.push(s.spell_type);
            if (s.casting_stat) smeta.push('Cast: ' + s.casting_stat);
            if (s.level) smeta.push('Lvl ' + s.level);
            if (s.target) smeta.push('Target: ' + s.target);
            if (s.duration) smeta.push('Duration: ' + s.duration);
            if (smeta.length) parts.push('<div class="text-muted small">' + smeta.join(' · ') + '</div>');
        }
        if (entityType === 'ability' && s.ability_kind) {
            var kindColor = s.ability_kind === 'starting' ? 'info' : s.ability_kind === 'milestone' ? 'warning' : 'danger';
            parts.push('<span class="badge bg-' + kindColor + '">' + s.ability_kind + '</span>');
        }
        if (entityType === 'path' && s.tiers) {
            var tierCount = Object.keys(s.tiers).length;
            parts.push('<div class="text-muted small">Tiers: ' + tierCount
                + (tierCount === 4 ? ' ✓' : '') + '</div>');
        }
        return parts.join('');
    }

    window.addIcrpgEntry = function (idx, overwrite) {
        var container = document.getElementById('icrpgAIResults');
        var suggestions = container._suggestions || [];
        var s = suggestions[idx];
        if (!s) return;

        var urlKey = ICRPG_URL_KEYS[icrpgAIEntity];
        var url = overwrite
            ? '/icrpg-catalog/' + urlKey + '/' + icrpgAIRethemeId + '/edit'
            : '/icrpg-catalog/' + urlKey + '/create';

        fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
            body: JSON.stringify(s)
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var card = document.getElementById('icrpg-card-' + idx);
            if (data.ok) {
                if (card) card.style.opacity = '0.6';
                var btns = card ? card.querySelectorAll('button') : [];
                btns.forEach(function (b) { b.disabled = true; });
                if (card) {
                    var ck = document.createElement('span');
                    ck.className = 'badge bg-success ms-2';
                    ck.textContent = overwrite ? 'Updated!' : 'Added!';
                    card.querySelector('.card-body').appendChild(ck);
                }
            } else {
                alert(data.error || 'Unknown error');
            }
        })
        .catch(function () { alert('Request failed. Check the browser console for details.'); });
    };

    // Delegated listener for Retheme buttons
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.icrpg-retheme-btn');
        if (!btn) return;
        var entityType = btn.dataset.entity;
        var entityId   = btn.dataset.id;
        var payload    = btn.dataset.payload;
        window.openIcrpgRetheme(entityType, entityId, payload);
    });

    // ── Tab persistence via URL hash ──────────────────────────────
    var tabButtons = document.querySelectorAll('#catalogTabs button[data-bs-toggle="tab"]');
    tabButtons.forEach(function (btn) {
        btn.addEventListener('shown.bs.tab', function () {
            window.location.hash = btn.getAttribute('data-bs-target').replace('#pane-', '');
        });
    });
    if (window.location.hash) {
        var hash = window.location.hash.substring(1);
        var target = document.querySelector('#catalogTabs button[data-bs-target="#pane-' + hash + '"]');
        if (target) {
            var tab = new bootstrap.Tab(target);
            tab.show();
        }
    }
})();

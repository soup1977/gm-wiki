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
                    field('bonuses', 'Bonuses (JSON)', typeof data.bonuses === 'object' ? JSON.stringify(data.bonuses) : (data.bonuses || ''),
                        'text', '{"STR": 1, "CON": 1, "CHA": -1}');
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
                    field('effects', 'Effects (JSON)',
                        typeof data.effects === 'object' ? JSON.stringify(data.effects) : (data.effects || ''),
                        'text', '{"DEFENSE": 2, "STR": 1, "WEAPON_EFFORT": 1}') +
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
                    field('tiers', 'Tiers (JSON array)', typeof data.tiers === 'object' ? JSON.stringify(data.tiers) : (data.tiers || '[]'),
                        'textarea', '[{"name": "Tier 1", "description": "First milestone"}]');
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
                var bonuses = v('bonuses');
                try { bonuses = bonuses ? JSON.parse(bonuses) : {}; }
                catch (e) { alert('Invalid bonuses JSON.'); return null; }
                data = { name: v('name'), description: v('description'),
                    world_id: parseInt(v('world-id')) || null, bonuses: bonuses };
                // Fix: the world select has id cf-world-id
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
                var effects = v('effects');
                try { effects = effects ? JSON.parse(effects) : {}; }
                catch (e) { alert('Invalid effects JSON.'); return null; }
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
                var tiers = v('tiers');
                try { tiers = tiers ? JSON.parse(tiers) : []; }
                catch (e) { alert('Invalid tiers JSON.'); return null; }
                data = { name: v('name'), description: v('description'), tiers: tiers };
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

    // ── Tab persistence via URL hash ──────────────────────────────
    var tabButtons = document.querySelectorAll('#catalogTabs button[data-bs-toggle="tab"]');
    tabButtons.forEach(function (btn) {
        btn.addEventListener('shown.bs.tab', function () {
            window.location.hash = btn.getAttribute('data-bs-target').replace('#pane-', '');
        });
    });
    // Restore tab from hash on load
    if (window.location.hash) {
        var hash = window.location.hash.substring(1);
        var target = document.querySelector('#catalogTabs button[data-bs-target="#pane-' + hash + '"]');
        if (target) {
            var tab = new bootstrap.Tab(target);
            tab.show();
        }
    }
})();

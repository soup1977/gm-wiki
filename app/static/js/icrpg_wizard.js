/**
 * ICRPG Character Creation Wizard
 * 9-step client-side wizard with embedded catalog data.
 */
(function () {
    'use strict';

    const TOTAL_STEPS = 9;
    const STAT_KEYS   = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
    const STAT_LABELS = {str:'STR', dex:'DEX', con:'CON', int:'INT', wis:'WIS', cha:'CHA'};
    const EFFORT_KEYS = ['basic', 'weapons', 'guns', 'magic', 'ultimate'];
    const EFFORT_LABELS = {basic:'Basic', weapons:'Weapons & Tools', guns:'Guns',
                           magic:'Magic', ultimate:'Ultimate'};
    const EFFORT_DICE = {basic:'d4', weapons:'d6', guns:'d8', magic:'d10', ultimate:'d12'};
    const MAX_STAT_PTS   = 6;
    const MAX_EFFORT_PTS = 4;
    const MAX_SINGLE_STAT   = 6;
    const MAX_SINGLE_EFFORT = 4;

    /* ── Wizard State ─────────────────────────────────────── */
    const wiz = {
        currentStep: 1,
        worldId: null,
        lifeFormId: null,
        typeId: null,
        stats:  {str:0, dex:0, con:0, int:0, wis:0, cha:0},
        effort: {basic:0, weapons:0, guns:0, magic:0, ultimate:0},
        abilityIds: [],
        lootPicks:  [],
        basicLootPicks: [],
    };

    /* ── Helpers ──────────────────────────────────────────── */
    function esc(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    function getCsrf() {
        const el = document.querySelector('meta[name="csrf-token"]');
        return el ? el.getAttribute('content') : '';
    }

    function showError(msg) {
        const el = document.getElementById('wizard-error');
        el.textContent = msg;
        el.classList.remove('d-none');
    }

    function clearError() {
        document.getElementById('wizard-error').classList.add('d-none');
    }

    function sumObj(obj) {
        return Object.values(obj).reduce((a, b) => a + b, 0);
    }

    function getWorldObj() {
        return CATALOG.worlds.find(w => w.id === wiz.worldId);
    }

    /* ── Step Navigation ──────────────────────────────────── */
    window.showStep = function (n) {
        // Auto-skip basic loot step if world has none
        if (n === 8) {
            const world = getWorldObj();
            const hasBasicLoot = world && world.basic_loot && world.basic_loot.length > 0;
            const maxPicks = world ? (world.basic_loot_count || 0) : 0;
            if (!hasBasicLoot || maxPicks === 0) {
                // Skip forward or backward depending on direction
                if (wiz.currentStep < 8) { n = 9; }
                else { n = 7; }
            }
        }

        document.querySelectorAll('.wizard-step').forEach(el => el.classList.add('d-none'));
        document.getElementById('step-' + n).classList.remove('d-none');
        document.getElementById('step-num').textContent = n;
        const bar = document.getElementById('wizard-progress');
        bar.style.width = ((n / TOTAL_STEPS) * 100) + '%';
        wiz.currentStep = n;
        clearError();
        window.scrollTo({top: 0, behavior: 'smooth'});

        // Render dynamic content for the step
        if (n === 1) renderWorldCards();
        if (n === 2) renderLifeFormCards();
        if (n === 3) renderTypeCards();
        if (n === 4) renderStatAllocator();
        if (n === 5) renderEffortAllocator();
        if (n === 6) renderAbilityPicker();
        if (n === 7) renderLootPicker();
        if (n === 8) renderBasicLootPicker();
        if (n === 9) renderReview();
    };

    window.goNext = function () {
        const s = wiz.currentStep;
        if (s === 1 && !wiz.worldId)    { showError('Please select a world.'); return; }
        if (s === 2 && !wiz.lifeFormId) { showError('Please select a life form.'); return; }
        if (s === 3 && !wiz.typeId)     { showError('Please select a type.'); return; }
        if (s === 4 && sumObj(wiz.stats) !== MAX_STAT_PTS) {
            showError('You must allocate exactly 6 stat points.'); return;
        }
        if (s === 5 && sumObj(wiz.effort) !== MAX_EFFORT_PTS) {
            showError('You must allocate exactly 4 effort points.'); return;
        }
        if (s === 6 && wiz.abilityIds.length === 0) {
            showError('Please select a starting ability.'); return;
        }
        if (s === 7 && wiz.lootPicks.length === 0) {
            showError('Please select a starting loot item.'); return;
        }
        if (s === 8) {
            const world = getWorldObj();
            const maxPicks = world ? (world.basic_loot_count || 0) : 0;
            if (wiz.basicLootPicks.length !== maxPicks) {
                showError('Please select exactly ' + maxPicks + ' basic loot items.'); return;
            }
        }
        showStep(s + 1);
    };

    window.goBack = function () {
        if (wiz.currentStep > 1) showStep(wiz.currentStep - 1);
    };

    /* ── Format Bonuses ───────────────────────────────────── */
    function formatBonuses(bonuses) {
        if (!bonuses || Object.keys(bonuses).length === 0) return '';
        const parts = [];
        for (const [k, v] of Object.entries(bonuses)) {
            if (k === 'ABILITY') {
                parts.push(v);
            } else if (k === 'HEARTS') {
                parts.push('+' + v + ' Heart' + (v > 1 ? 's' : ''));
            } else if (k === 'DEFENSE') {
                parts.push('+' + v + ' Defense');
            } else if (k.endsWith('_EFFORT')) {
                const name = k.replace('_EFFORT', '').toLowerCase();
                const label = EFFORT_LABELS[name] || name;
                parts.push('+' + v + ' ' + label + ' Effort');
            } else {
                // Stat bonus (STR, DEX, etc.)
                const sign = v >= 0 ? '+' : '';
                parts.push(sign + v + ' ' + k);
            }
        }
        return parts.join(', ');
    }

    function getLfBonuses() {
        if (!wiz.lifeFormId) return {};
        const lf = CATALOG.life_forms.find(l => l.id === wiz.lifeFormId);
        return (lf && lf.bonuses) || {};
    }

    function getStatBonus(statKey) {
        const bonuses = getLfBonuses();
        return parseInt(bonuses[statKey.toUpperCase()] || 0, 10) || 0;
    }

    function getEffortBonus(effortKey) {
        const bonuses = getLfBonuses();
        return parseInt(bonuses[effortKey.toUpperCase() + '_EFFORT'] || 0, 10) || 0;
    }

    /* ── Selection Card Builder ───────────────────────────── */
    function buildSelectionCards(container, items, selectedId, onSelect, extraHtml) {
        container.innerHTML = '';
        items.forEach(item => {
            const col = document.createElement('div');
            col.className = 'col-md-6';
            const selected = item.id === selectedId;
            col.innerHTML = `
                <div class="card bg-dark border-secondary icrpg-wizard-card
                            ${selected ? 'border-warning' : ''}"
                     data-id="${item.id}" style="cursor:pointer;">
                    <div class="card-body">
                        <h6 class="card-title mb-1">${esc(item.name)}</h6>
                        ${item.description ? '<p class="card-text text-muted small mb-1">' + esc(item.description) + '</p>' : ''}
                        ${extraHtml ? extraHtml(item) : ''}
                    </div>
                </div>`;
            col.querySelector('.card').addEventListener('click', function () {
                container.querySelectorAll('.card').forEach(c => c.classList.remove('border-warning'));
                this.classList.add('border-warning');
                onSelect(item);
            });
            container.appendChild(col);
        });
    }

    /* ── Step 1: World ────────────────────────────────────── */
    function renderWorldCards() {
        const container = document.getElementById('world-cards');
        buildSelectionCards(container, CATALOG.worlds, wiz.worldId, function (item) {
            if (item.id !== wiz.worldId) {
                wiz.worldId = item.id;
                // Cascade reset
                wiz.lifeFormId = null;
                wiz.typeId = null;
                wiz.abilityIds = [];
                wiz.lootPicks = [];
                wiz.basicLootPicks = [];
            }
            document.getElementById('btn-next-1').disabled = false;
        });
    }

    /* ── Step 2: Life Form ────────────────────────────────── */
    function renderLifeFormCards() {
        const filtered = CATALOG.life_forms.filter(lf => lf.world_id === wiz.worldId);
        const container = document.getElementById('lifeform-cards');
        const noMsg = document.getElementById('no-lifeforms');
        const btn = document.getElementById('btn-next-2');

        if (filtered.length === 0) {
            container.innerHTML = '';
            noMsg.classList.remove('d-none');
            btn.disabled = true;
            return;
        }
        noMsg.classList.add('d-none');

        buildSelectionCards(container, filtered, wiz.lifeFormId, function (item) {
            wiz.lifeFormId = item.id;
            btn.disabled = false;
        }, function (item) {
            const bonus = formatBonuses(item.bonuses);
            return bonus ? '<span class="badge bg-info text-dark small">' + esc(bonus) + '</span>' : '';
        });

        btn.disabled = !wiz.lifeFormId;
    }

    /* ── Step 3: Type ─────────────────────────────────────── */
    function renderTypeCards() {
        const filtered = CATALOG.types.filter(t => t.world_id === wiz.worldId);
        const container = document.getElementById('type-cards');
        const noMsg = document.getElementById('no-types');
        const btn = document.getElementById('btn-next-3');

        if (filtered.length === 0) {
            container.innerHTML = '';
            noMsg.classList.remove('d-none');
            btn.disabled = true;
            return;
        }
        noMsg.classList.add('d-none');

        buildSelectionCards(container, filtered, wiz.typeId, function (item) {
            if (item.id !== wiz.typeId) {
                wiz.typeId = item.id;
                // Reset downstream
                wiz.abilityIds = [];
                wiz.lootPicks = [];
            }
            btn.disabled = false;
        }, function (item) {
            let html = '';
            if (item.starting_abilities && item.starting_abilities.length) {
                html += '<div class="mt-2 small text-muted">';
                html += '<strong>Abilities:</strong> ';
                html += item.starting_abilities.map(a => esc(a.name)).join(', ');
                html += '</div>';
            }
            if (item.starting_loot && item.starting_loot.length) {
                html += '<div class="small text-muted">';
                html += '<strong>Loot:</strong> ';
                html += item.starting_loot.map(l => esc(l.name)).join(', ');
                html += '</div>';
            }
            return html;
        });

        btn.disabled = !wiz.typeId;
    }

    /* ── Step 4: Stats ────────────────────────────────────── */
    function renderStatAllocator() {
        const tbody = document.getElementById('stat-rows');
        tbody.innerHTML = '';
        const bonuses = getLfBonuses();

        // Show life form bonus info
        const infoEl = document.getElementById('lf-bonus-info');
        const abilityBonus = bonuses.ABILITY;
        if (abilityBonus) {
            infoEl.innerHTML = '<i class="bi bi-star me-1"></i><strong>Life Form Ability:</strong> ' + esc(abilityBonus);
            infoEl.classList.remove('d-none');
        } else {
            infoEl.classList.add('d-none');
        }

        STAT_KEYS.forEach(key => {
            const label = STAT_LABELS[key];
            const raceBonus = getStatBonus(key);
            const base = wiz.stats[key];
            const total = base + raceBonus;
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="fw-bold">${label}</td>
                <td class="text-center" style="width:160px;">
                    <div class="d-flex align-items-center justify-content-center gap-2">
                        <button class="btn btn-sm btn-outline-secondary stat-minus"
                                data-key="${key}">-</button>
                        <span class="stat-base fw-bold" id="stat-base-${key}"
                              style="min-width:24px; display:inline-block; text-align:center;">${base}</span>
                        <button class="btn btn-sm btn-outline-secondary stat-plus"
                                data-key="${key}">+</button>
                    </div>
                </td>
                <td class="text-center text-muted">${raceBonus ? (raceBonus > 0 ? '+' : '') + raceBonus : '—'}</td>
                <td class="text-center fw-bold" id="stat-total-${key}">${total}</td>`;
            tbody.appendChild(tr);
        });

        // Wire up +/- buttons
        tbody.querySelectorAll('.stat-minus').forEach(btn => {
            btn.addEventListener('click', function () {
                const k = this.dataset.key;
                if (wiz.stats[k] > 0) {
                    wiz.stats[k]--;
                    updateStatDisplay();
                }
            });
        });
        tbody.querySelectorAll('.stat-plus').forEach(btn => {
            btn.addEventListener('click', function () {
                const k = this.dataset.key;
                if (wiz.stats[k] < MAX_SINGLE_STAT && sumObj(wiz.stats) < MAX_STAT_PTS) {
                    wiz.stats[k]++;
                    updateStatDisplay();
                }
            });
        });
        updateStatDisplay();
    }

    function updateStatDisplay() {
        const used = sumObj(wiz.stats);
        const left = MAX_STAT_PTS - used;
        document.getElementById('stat-points-left').textContent = left;

        STAT_KEYS.forEach(key => {
            const base = wiz.stats[key];
            const bonus = getStatBonus(key);
            document.getElementById('stat-base-' + key).textContent = base;
            document.getElementById('stat-total-' + key).textContent = base + bonus;
        });

        document.getElementById('btn-next-4').disabled = (used !== MAX_STAT_PTS);
    }

    /* ── Step 5: Effort ───────────────────────────────────── */
    function renderEffortAllocator() {
        const tbody = document.getElementById('effort-rows');
        tbody.innerHTML = '';

        EFFORT_KEYS.forEach(key => {
            const label = EFFORT_LABELS[key];
            const die = EFFORT_DICE[key];
            const base = wiz.effort[key];
            const bonus = getEffortBonus(key);
            const total = base + bonus;
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="fw-bold">${esc(label)}</td>
                <td class="text-center text-muted">${die}</td>
                <td class="text-center">
                    <div class="d-flex align-items-center justify-content-center gap-2">
                        <button class="btn btn-sm btn-outline-secondary effort-minus"
                                data-key="${key}">-</button>
                        <span class="fw-bold" id="effort-base-${key}"
                              style="min-width:24px; display:inline-block; text-align:center;">${base}</span>
                        <button class="btn btn-sm btn-outline-secondary effort-plus"
                                data-key="${key}">+</button>
                    </div>
                </td>
                <td class="text-center text-muted">${bonus ? '+' + bonus : '—'}</td>
                <td class="text-center fw-bold" id="effort-total-${key}">${total}</td>`;
            tbody.appendChild(tr);
        });

        tbody.querySelectorAll('.effort-minus').forEach(btn => {
            btn.addEventListener('click', function () {
                const k = this.dataset.key;
                if (wiz.effort[k] > 0) {
                    wiz.effort[k]--;
                    updateEffortDisplay();
                }
            });
        });
        tbody.querySelectorAll('.effort-plus').forEach(btn => {
            btn.addEventListener('click', function () {
                const k = this.dataset.key;
                if (wiz.effort[k] < MAX_SINGLE_EFFORT && sumObj(wiz.effort) < MAX_EFFORT_PTS) {
                    wiz.effort[k]++;
                    updateEffortDisplay();
                }
            });
        });
        updateEffortDisplay();
    }

    function updateEffortDisplay() {
        const used = sumObj(wiz.effort);
        const left = MAX_EFFORT_PTS - used;
        document.getElementById('effort-points-left').textContent = left;

        EFFORT_KEYS.forEach(key => {
            const base = wiz.effort[key];
            const bonus = getEffortBonus(key);
            document.getElementById('effort-base-' + key).textContent = base;
            document.getElementById('effort-total-' + key).textContent = base + bonus;
        });

        document.getElementById('btn-next-5').disabled = (used !== MAX_EFFORT_PTS);
    }

    /* ── Step 6: Starting Ability ─────────────────────────── */
    function renderAbilityPicker() {
        const typeObj = CATALOG.types.find(t => t.id === wiz.typeId);
        const abilities = typeObj ? typeObj.starting_abilities : [];
        const container = document.getElementById('ability-cards');
        const btn = document.getElementById('btn-next-6');

        // Auto-select if only one
        if (abilities.length === 1 && wiz.abilityIds.length === 0) {
            wiz.abilityIds = [abilities[0].id];
        }

        const selectedId = wiz.abilityIds.length ? wiz.abilityIds[0] : null;
        buildSelectionCards(container, abilities, selectedId, function (item) {
            wiz.abilityIds = [item.id];
            btn.disabled = false;
        });

        btn.disabled = wiz.abilityIds.length === 0;
    }

    /* ── Step 7: Starting Loot ────────────────────────────── */
    function renderLootPicker() {
        const typeObj = CATALOG.types.find(t => t.id === wiz.typeId);
        const loot = typeObj ? typeObj.starting_loot : [];
        const container = document.getElementById('loot-cards');
        const btn = document.getElementById('btn-next-7');

        // Auto-select if only one
        if (loot.length === 1 && wiz.lootPicks.length === 0) {
            wiz.lootPicks = [{loot_def_id: loot[0].loot_def_id, spell_id: loot[0].spell_id}];
        }

        const selectedId = wiz.lootPicks.length ? findLootSelectedId(loot) : null;

        buildSelectionCards(container, loot, selectedId, function (item) {
            wiz.lootPicks = [{loot_def_id: item.loot_def_id, spell_id: item.spell_id}];
            btn.disabled = false;
        }, function (item) {
            if (item.loot_type) {
                return '<span class="badge bg-secondary small">' + esc(item.loot_type) + '</span>';
            }
            return '';
        });

        btn.disabled = wiz.lootPicks.length === 0;
    }

    function findLootSelectedId(lootList) {
        if (!wiz.lootPicks.length) return null;
        const pick = wiz.lootPicks[0];
        const match = lootList.find(l =>
            l.loot_def_id === pick.loot_def_id && l.spell_id === pick.spell_id);
        return match ? match.id : null;
    }

    /* ── Step 8: Basic World Loot (multi-select) ──────────── */
    function renderBasicLootPicker() {
        const world = getWorldObj();
        const loot = world ? (world.basic_loot || []) : [];
        const maxPicks = world ? (world.basic_loot_count || 4) : 4;
        const container = document.getElementById('basic-loot-cards');
        const btn = document.getElementById('btn-next-8');
        const noMsg = document.getElementById('no-basic-loot');
        const countEl = document.getElementById('basic-loot-count');
        const maxEl = document.getElementById('basic-loot-max');

        maxEl.textContent = maxPicks;

        if (loot.length === 0) {
            container.innerHTML = '';
            noMsg.classList.remove('d-none');
            btn.disabled = true;
            return;
        }
        noMsg.classList.add('d-none');

        // Build multi-select cards
        container.innerHTML = '';
        loot.forEach(function (item) {
            const col = document.createElement('div');
            col.className = 'col-md-6';
            const selected = wiz.basicLootPicks.indexOf(item.id) !== -1;
            col.innerHTML =
                '<div class="card bg-dark border-secondary icrpg-wizard-card' +
                (selected ? ' border-warning' : '') + '"' +
                ' data-id="' + item.id + '" style="cursor:pointer;">' +
                '<div class="card-body">' +
                '<h6 class="card-title mb-1">' + esc(item.name) + '</h6>' +
                (item.description ? '<p class="card-text text-muted small mb-1">' + esc(item.description) + '</p>' : '') +
                (item.loot_type ? '<span class="badge bg-secondary small">' + esc(item.loot_type) + '</span>' : '') +
                '</div></div>';

            col.querySelector('.card').addEventListener('click', function () {
                var idx = wiz.basicLootPicks.indexOf(item.id);
                if (idx !== -1) {
                    // Deselect
                    wiz.basicLootPicks.splice(idx, 1);
                    this.classList.remove('border-warning');
                } else if (wiz.basicLootPicks.length < maxPicks) {
                    // Select
                    wiz.basicLootPicks.push(item.id);
                    this.classList.add('border-warning');
                }
                countEl.textContent = wiz.basicLootPicks.length;
                btn.disabled = (wiz.basicLootPicks.length !== maxPicks);
            });
            container.appendChild(col);
        });

        countEl.textContent = wiz.basicLootPicks.length;
        btn.disabled = (wiz.basicLootPicks.length !== maxPicks);
    }

    /* ── Step 9: Review ───────────────────────────────────── */
    function renderReview() {
        const world = CATALOG.worlds.find(w => w.id === wiz.worldId);
        const lf = CATALOG.life_forms.find(l => l.id === wiz.lifeFormId);
        const typeObj = CATALOG.types.find(t => t.id === wiz.typeId);
        const ability = typeObj ? typeObj.starting_abilities.find(a => wiz.abilityIds.includes(a.id)) : null;
        const lootItem = typeObj && wiz.lootPicks.length ?
            typeObj.starting_loot.find(l =>
                l.loot_def_id === wiz.lootPicks[0].loot_def_id &&
                l.spell_id === wiz.lootPicks[0].spell_id) : null;

        let html = '<table class="table table-dark table-sm mb-3">';
        html += `<tr><td class="text-muted">World</td><td>${esc(world ? world.name : '—')}</td></tr>`;
        html += `<tr><td class="text-muted">Life Form</td><td>${esc(lf ? lf.name : '—')}`;
        if (lf && lf.bonuses) {
            const bonus = formatBonuses(lf.bonuses);
            if (bonus) html += ` <span class="text-info small">(${esc(bonus)})</span>`;
        }
        html += `</td></tr>`;
        html += `<tr><td class="text-muted">Type</td><td>${esc(typeObj ? typeObj.name : '—')}</td></tr>`;
        html += '</table>';

        // Stats with totals
        html += '<h6>Stats</h6><table class="table table-dark table-sm mb-3">';
        html += '<thead><tr><th>Stat</th><th class="text-center">Base</th><th class="text-center">Race</th><th class="text-center">Total</th></tr></thead><tbody>';
        STAT_KEYS.forEach(key => {
            const base = wiz.stats[key];
            const bonus = getStatBonus(key);
            html += `<tr><td>${STAT_LABELS[key]}</td>
                     <td class="text-center">${base}</td>
                     <td class="text-center text-muted">${bonus ? (bonus > 0 ? '+' : '') + bonus : '—'}</td>
                     <td class="text-center fw-bold">${base + bonus}</td></tr>`;
        });
        html += '</tbody></table>';

        // Effort
        html += '<h6>Effort</h6><table class="table table-dark table-sm mb-3">';
        html += '<thead><tr><th>Effort</th><th class="text-center">Die</th><th class="text-center">Base</th><th class="text-center">Total</th></tr></thead><tbody>';
        EFFORT_KEYS.forEach(key => {
            const base = wiz.effort[key];
            const bonus = getEffortBonus(key);
            html += `<tr><td>${esc(EFFORT_LABELS[key])}</td>
                     <td class="text-center text-muted">${EFFORT_DICE[key]}</td>
                     <td class="text-center">${base}</td>
                     <td class="text-center fw-bold">${base + bonus}</td></tr>`;
        });
        html += '</tbody></table>';

        // Ability & Type Loot
        html += '<div class="row g-3">';
        html += '<div class="col-sm-6"><h6>Starting Ability</h6>';
        if (ability) {
            html += `<p class="mb-0"><strong>${esc(ability.name)}</strong></p>`;
            if (ability.description) html += `<p class="text-muted small">${esc(ability.description)}</p>`;
        }
        html += '</div>';
        html += '<div class="col-sm-6"><h6>Type Loot</h6>';
        if (lootItem) {
            html += `<p class="mb-0"><strong>${esc(lootItem.name)}</strong>`;
            if (lootItem.loot_type) html += ` <span class="badge bg-secondary small">${esc(lootItem.loot_type)}</span>`;
            html += '</p>';
            if (lootItem.description) html += `<p class="text-muted small">${esc(lootItem.description)}</p>`;
        }
        html += '</div></div>';

        // Basic Loot
        if (wiz.basicLootPicks.length > 0 && world && world.basic_loot) {
            html += '<h6 class="mt-3">Basic Loot</h6>';
            html += '<ul class="list-unstyled">';
            wiz.basicLootPicks.forEach(function (pickId) {
                var item = world.basic_loot.find(function (l) { return l.id === pickId; });
                if (item) {
                    html += '<li><strong>' + esc(item.name) + '</strong>';
                    if (item.loot_type) html += ' <span class="badge bg-secondary small">' + esc(item.loot_type) + '</span>';
                    html += '</li>';
                }
            });
            html += '</ul>';
        }

        document.getElementById('review-summary').innerHTML = html;
    }

    /* ── Submit ────────────────────────────────────────────── */
    window.submitCharacter = function () {
        const charName = document.getElementById('inp-charname').value.trim();
        const playerName = document.getElementById('inp-playername').value.trim();
        const story = document.getElementById('inp-story').value.trim();

        if (!charName || !playerName) {
            showError('Character name and player name are required.');
            return;
        }

        const btn = document.getElementById('btn-create');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Creating...';
        clearError();

        const payload = {
            character_name: charName,
            player_name: playerName,
            story: story,
            world_id: wiz.worldId,
            life_form_id: wiz.lifeFormId,
            type_id: wiz.typeId,
            stats: wiz.stats,
            effort: wiz.effort,
            ability_ids: wiz.abilityIds,
            loot_picks: wiz.lootPicks,
            basic_loot_picks: wiz.basicLootPicks,
        };

        fetch('/pcs/icrpg/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf(),
            },
            body: JSON.stringify(payload),
        })
        .then(r => r.json())
        .then(data => {
            if (data.ok) {
                window.location.href = data.redirect;
            } else {
                showError(data.error || 'Something went wrong.');
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-check-circle me-1"></i> Create Character';
            }
        })
        .catch(err => {
            showError('Network error: ' + err.message);
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-check-circle me-1"></i> Create Character';
        });
    };

    /* ── Init ─────────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', function () {
        showStep(1);
    });

})();

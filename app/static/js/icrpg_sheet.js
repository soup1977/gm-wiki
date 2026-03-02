/**
 * icrpg_sheet.js
 * AJAX quick-edit handlers for the ICRPG character sheet.
 * Follows the IIFE pattern used by other War Table JS modules.
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var dataEl = document.getElementById('icrpg-data');
        if (!dataEl) return;

        var pcId = dataEl.dataset.pcId;
        var canEdit = dataEl.dataset.canEdit === 'true';
        var csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

        if (!canEdit) return;

        // ── Helper: POST JSON to an ICRPG endpoint ──────────────
        function postAction(action, body, callback) {
            fetch('/pcs/' + pcId + '/icrpg/' + action, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify(body),
            })
            .then(function (r) {
                return r.json().then(function (data) {
                    return { ok: r.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok || result.data.error) {
                    var msg = result.data.error || 'Something went wrong.';
                    console.error('ICRPG error:', msg);
                    alert(msg);
                    return;
                }
                callback(result.data);
            })
            .catch(function (err) {
                console.error('ICRPG request failed:', err);
            });
        }

        // ── HP helpers ─────────────────────────────────────────
        function updateHpDisplay(data) {
            document.getElementById('icrpg-hp-current').textContent = data.hp_current;
            document.getElementById('icrpg-hp-max').textContent = data.hp_max;
            var pct = data.hp_max > 0 ? Math.round((data.hp_current / data.hp_max) * 100) : 0;
            var bar = document.getElementById('icrpg-hp-bar');
            bar.style.width = pct + '%';
            bar.setAttribute('aria-valuenow', data.hp_current);
            bar.className = 'progress-bar';
            if (pct > 50) bar.classList.add('bg-success');
            else if (pct > 25) bar.classList.add('bg-warning');
            else bar.classList.add('bg-danger');
        }

        // ── HP adjustment ───────────────────────────────────────
        document.querySelectorAll('.icrpg-hp-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                postAction('hp', { delta: parseInt(btn.dataset.delta) }, updateHpDisplay);
            });
        });

        // ── HP reset to max ─────────────────────────────────────
        var hpResetBtn = document.getElementById('icrpg-hp-reset');
        if (hpResetBtn) {
            hpResetBtn.addEventListener('click', function () {
                postAction('hp', { reset: true }, updateHpDisplay);
            });
        }

        // ── Coin adjustment ─────────────────────────────────────
        document.querySelectorAll('.icrpg-coin-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                postAction('coin', { delta: parseInt(btn.dataset.delta) }, function (data) {
                    document.getElementById('icrpg-coin').textContent = data.coin;
                });
            });
        });

        // ── Inline edit for HP and Coin ─────────────────────────
        function makeEditable(el, action, bodyKey, onSave) {
            if (!el || !el.classList.contains('icrpg-editable')) return;
            el.style.cursor = 'pointer';
            el.style.borderBottom = '1px dashed rgba(255,255,255,0.3)';
            el.addEventListener('click', function () {
                if (el.querySelector('input')) return;
                var current = el.textContent.trim();
                var input = document.createElement('input');
                input.type = 'number';
                input.value = current;
                input.className = 'form-control form-control-sm bg-dark text-light border-secondary text-center';
                input.style.width = '4em';
                input.style.display = 'inline-block';
                el.textContent = '';
                el.appendChild(input);
                input.focus();
                input.select();
                function save() {
                    var val = parseInt(input.value) || 0;
                    var body = {};
                    body[bodyKey] = val;
                    postAction(action, body, function (data) {
                        onSave(data);
                    });
                }
                input.addEventListener('keydown', function (e) {
                    if (e.key === 'Enter') { e.preventDefault(); save(); }
                    if (e.key === 'Escape') { el.textContent = current; }
                });
                input.addEventListener('blur', save);
            });
        }

        makeEditable(document.getElementById('icrpg-hp-current'), 'hp', 'value', function (data) {
            updateHpDisplay(data);
        });
        makeEditable(document.getElementById('icrpg-coin'), 'coin', 'value', function (data) {
            document.getElementById('icrpg-coin').textContent = data.coin;
        });

        // ── Hero Coin toggle ────────────────────────────────────
        var coinBtn = document.getElementById('icrpg-hero-coin-btn');
        if (coinBtn) {
            coinBtn.addEventListener('click', function () {
                postAction('hero-coin', {}, function (data) {
                    var icon = coinBtn.querySelector('i');
                    if (data.hero_coin) {
                        coinBtn.classList.remove('btn-outline-secondary');
                        coinBtn.classList.add('btn-warning');
                        icon.className = 'bi bi-circle-fill';
                        coinBtn.lastChild.textContent = ' Active';
                    } else {
                        coinBtn.classList.remove('btn-warning');
                        coinBtn.classList.add('btn-outline-secondary');
                        icon.className = 'bi bi-circle';
                        coinBtn.lastChild.textContent = ' Spent';
                    }
                });
            });
        }

        // ── Dying Timer ─────────────────────────────────────────
        document.querySelectorAll('.icrpg-dying-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var delta = parseInt(btn.dataset.delta);
                postAction('dying', { delta: delta }, function (data) {
                    for (var i = 1; i <= 3; i++) {
                        var pip = document.getElementById('icrpg-dying-pip-' + i);
                        if (pip) {
                            if (i <= data.dying_timer) {
                                pip.className = 'bi bi-circle-fill text-danger me-1';
                            } else {
                                pip.className = 'bi bi-circle text-secondary me-1';
                            }
                        }
                    }
                });
            });
        });

        // ── Nat 20 increment ────────────────────────────────────
        var nat20Btn = document.getElementById('icrpg-nat20-btn');
        if (nat20Btn) {
            nat20Btn.addEventListener('click', function () {
                postAction('nat20', {}, function (data) {
                    document.getElementById('icrpg-nat20-count').textContent = data.nat20_count;
                    document.getElementById('icrpg-mastery-count').textContent = data.mastery_count;
                    // Update progress bar
                    var bar = nat20Btn.closest('.card-body').querySelector('.progress-bar');
                    if (bar) {
                        bar.style.width = Math.round((data.nat20_count / 20) * 100) + '%';
                    }
                });
            });
        }

        // ── Equip / Unequip ─────────────────────────────────────
        document.querySelectorAll('.icrpg-equip-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var lootId = parseInt(btn.dataset.lootId);
                var newSlot = btn.dataset.newSlot;
                postAction('equip', { loot_id: lootId, slot: newSlot }, function () {
                    window.location.reload();
                });
            });
        });

        // ── Stat adjustment (GM only) ─────────────────────────────
        document.querySelectorAll('.icrpg-stat-adj').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var key = btn.dataset.key;
                var delta = parseInt(btn.dataset.delta);
                postAction('update-stat', { key: key, delta: delta }, function (data) {
                    // Update base value
                    var cell = document.getElementById('icrpg-stat-base-' + key.toLowerCase());
                    if (cell) {
                        var valSpan = cell.querySelector('.icrpg-stat-base-val');
                        if (valSpan) valSpan.textContent = data.base;
                    }
                    // Update total
                    var totalEl = document.getElementById('icrpg-stat-' + data.key);
                    if (totalEl) totalEl.textContent = data.total;
                    // Update defense if CON changed
                    var defEl = document.getElementById('icrpg-defense');
                    if (defEl) defEl.textContent = data.defense;
                });
            });
        });

        // ── Effort adjustment (GM only) ───────────────────────────
        document.querySelectorAll('.icrpg-effort-adj').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var key = btn.dataset.key;
                var delta = parseInt(btn.dataset.delta);
                postAction('update-effort', { key: key, delta: delta }, function (data) {
                    var cell = document.getElementById('icrpg-effort-base-' + data.key);
                    if (cell) {
                        var valSpan = cell.querySelector('.icrpg-effort-base-val');
                        if (valSpan) valSpan.textContent = data.base;
                    }
                    var totalEl = document.getElementById('icrpg-effort-' + data.key);
                    if (totalEl) totalEl.textContent = data.total;
                });
            });
        });

        // ── Remove Loot ─────────────────────────────────────────
        document.querySelectorAll('.icrpg-remove-loot-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                if (!confirm('Remove this item?')) return;
                var lootId = parseInt(btn.dataset.lootId);
                postAction('remove-loot', { loot_id: lootId }, function () {
                    window.location.reload();
                });
            });
        });

        // ── Remove Ability ──────────────────────────────────────
        document.querySelectorAll('.icrpg-remove-ability-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                if (!confirm('Remove this ability?')) return;
                var abId = parseInt(btn.dataset.abilityId);
                postAction('remove-ability', { ability_id: abId }, function () {
                    window.location.reload();
                });
            });
        });

        // ── Allow Player Edit toggle (GM only) ──────────────────
        var playerEditToggle = document.getElementById('icrpg-allow-player-edit');
        if (playerEditToggle) {
            playerEditToggle.addEventListener('change', function () {
                postAction('toggle-player-edit', {}, function () {
                    window.location.reload();
                });
            });
        }

        // ── Notes tab (auto-save on change) ──────────────────────
        var notesEditor = document.getElementById('icrpg-notes-editor');
        var saveNotesBtn = document.getElementById('icrpg-save-notes-btn');
        if (notesEditor && saveNotesBtn) {
            var notesSaveTimer = null;
            function saveNotes() {
                postAction('notes', { notes: notesEditor.value }, function () {
                    saveNotesBtn.classList.add('d-none');
                });
            }
            notesEditor.addEventListener('input', function () {
                saveNotesBtn.classList.remove('d-none');
                clearTimeout(notesSaveTimer);
                notesSaveTimer = setTimeout(saveNotes, 1500);
            });
            saveNotesBtn.addEventListener('click', function () {
                clearTimeout(notesSaveTimer);
                saveNotes();
            });
        }

        // ── Add Loot Modal ──────────────────────────────────────
        if (typeof SHEET_CATALOG !== 'undefined') {
            var addLootModal = document.getElementById('addLootModal');
            var lootTypeFilter = document.getElementById('loot-type-filter');
            var lootSearch = document.getElementById('loot-search');
            var lootCatalogSelect = document.getElementById('loot-catalog-select');
            var lootCatalogDesc = document.getElementById('loot-catalog-desc');
            var spellCatalogSelect = document.getElementById('spell-catalog-select');
            var spellCatalogDesc = document.getElementById('spell-catalog-desc');
            var spellStatFilter = document.getElementById('spell-stat-filter');
            var spellSearch = document.getElementById('spell-search');
            var lootSlotSelect = document.getElementById('loot-slot-select');

            // Populate loot type filter options
            var lootTypes = {};
            SHEET_CATALOG.loot_defs.forEach(function (ld) {
                if (ld.loot_type) lootTypes[ld.loot_type] = true;
            });
            Object.keys(lootTypes).sort().forEach(function (t) {
                var opt = document.createElement('option');
                opt.value = t; opt.textContent = t;
                lootTypeFilter.appendChild(opt);
            });

            function populateLootSelect() {
                var filter = lootTypeFilter.value;
                var search = (lootSearch.value || '').toLowerCase();
                lootCatalogSelect.innerHTML = '';
                lootCatalogDesc.textContent = '';
                SHEET_CATALOG.loot_defs.forEach(function (ld) {
                    if (filter && ld.loot_type !== filter) return;
                    if (search && ld.name.toLowerCase().indexOf(search) === -1 &&
                        (ld.description || '').toLowerCase().indexOf(search) === -1) return;
                    var opt = document.createElement('option');
                    opt.value = ld.id;
                    var label = ld.name;
                    if (ld.loot_type) label += ' (' + ld.loot_type + ')';
                    if (ld.slot_cost && ld.slot_cost !== 1) label += ' [' + ld.slot_cost + ' slots]';
                    opt.textContent = label;
                    opt.dataset.desc = ld.description;
                    lootCatalogSelect.appendChild(opt);
                });
            }

            function populateSpellSelect() {
                var filter = spellStatFilter ? spellStatFilter.value : '';
                var search = (spellSearch.value || '').toLowerCase();
                spellCatalogSelect.innerHTML = '';
                spellCatalogDesc.textContent = '';
                SHEET_CATALOG.spells.forEach(function (sp) {
                    if (filter && sp.casting_stat !== filter) return;
                    if (search && sp.name.toLowerCase().indexOf(search) === -1 &&
                        (sp.description || '').toLowerCase().indexOf(search) === -1) return;
                    var opt = document.createElement('option');
                    opt.value = sp.id;
                    var label = sp.name;
                    if (sp.spell_type) label += ' (' + sp.spell_type + ')';
                    if (sp.casting_stat) label += ' [' + sp.casting_stat + ']';
                    opt.textContent = label;
                    opt.dataset.desc = sp.description;
                    spellCatalogSelect.appendChild(opt);
                });
            }

            populateLootSelect();
            populateSpellSelect();

            lootTypeFilter.addEventListener('change', populateLootSelect);
            lootSearch.addEventListener('input', populateLootSelect);
            if (spellStatFilter) {
                spellStatFilter.addEventListener('change', populateSpellSelect);
            }
            spellSearch.addEventListener('input', populateSpellSelect);

            lootCatalogSelect.addEventListener('change', function () {
                var sel = lootCatalogSelect.options[lootCatalogSelect.selectedIndex];
                lootCatalogDesc.textContent = sel ? (sel.dataset.desc || '') : '';
            });

            spellCatalogSelect.addEventListener('change', function () {
                var sel = spellCatalogSelect.options[spellCatalogSelect.selectedIndex];
                spellCatalogDesc.textContent = sel ? (sel.dataset.desc || '') : '';
            });

            // Open modal with default slot from trigger button
            document.querySelectorAll('.icrpg-open-add-loot').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    lootSlotSelect.value = btn.dataset.defaultSlot || 'carried';
                    var modal = new bootstrap.Modal(addLootModal);
                    modal.show();
                });
            });

            // Submit Add Loot
            document.getElementById('btn-add-loot').addEventListener('click', function () {
                var activeTab = addLootModal.querySelector('.tab-pane.active');
                var body = { slot: lootSlotSelect.value };

                if (activeTab.id === 'loot-tab-catalog') {
                    if (!lootCatalogSelect.value) { alert('Select an item.'); return; }
                    body.loot_def_id = parseInt(lootCatalogSelect.value);
                } else if (activeTab.id === 'loot-tab-spell') {
                    if (!spellCatalogSelect.value) { alert('Select a spell.'); return; }
                    body.spell_id = parseInt(spellCatalogSelect.value);
                } else {
                    var name = document.getElementById('custom-loot-name').value.trim();
                    if (!name) { alert('Enter a name.'); return; }
                    body.custom_name = name;
                    body.custom_desc = document.getElementById('custom-loot-desc').value.trim();
                }

                postAction('add-loot', body, function () {
                    window.location.reload();
                });
            });

            // ── Add Ability Modal ───────────────────────────────────
            var abilityKindFilter = document.getElementById('ability-kind-filter');
            var abilityTypeFilter = document.getElementById('ability-type-filter');
            var abilityMyTypeOnly = document.getElementById('ability-my-type-only');
            var abilityCatalogSelect = document.getElementById('ability-catalog-select');
            var abilityCatalogDesc = document.getElementById('ability-catalog-desc');

            // Populate ability type filter from catalog
            var abilityTypes = {};
            SHEET_CATALOG.abilities.forEach(function (ab) {
                if (ab.type_name) abilityTypes[ab.type_id] = ab.type_name;
            });
            Object.keys(abilityTypes).forEach(function (tid) {
                var opt = document.createElement('option');
                opt.value = tid;
                opt.textContent = abilityTypes[tid];
                abilityTypeFilter.appendChild(opt);
            });

            function populateAbilitySelect() {
                var kindFilter = abilityKindFilter.value;
                var typeFilter = abilityTypeFilter.value;
                var myTypeOnly = abilityMyTypeOnly && abilityMyTypeOnly.checked;
                var charTypeId = SHEET_CATALOG.char_type_id;

                abilityCatalogSelect.innerHTML = '';
                abilityCatalogDesc.textContent = '';
                SHEET_CATALOG.abilities.forEach(function (ab) {
                    if (kindFilter && ab.ability_kind !== kindFilter) return;
                    // Type filtering: explicit dropdown takes priority, then checkbox
                    if (typeFilter) {
                        if (String(ab.type_id) !== typeFilter) return;
                    } else if (myTypeOnly && charTypeId) {
                        if (ab.type_id && ab.type_id !== charTypeId) return;
                    }
                    var opt = document.createElement('option');
                    opt.value = ab.id;
                    opt.textContent = ab.name + (ab.type_name ? ' (' + ab.type_name + ')' : '') + ' [' + ab.ability_kind + ']';
                    opt.dataset.desc = ab.description;
                    abilityCatalogSelect.appendChild(opt);
                });
            }

            populateAbilitySelect();
            abilityKindFilter.addEventListener('change', populateAbilitySelect);
            abilityTypeFilter.addEventListener('change', function () {
                // If a specific type is selected, uncheck "My type only"
                if (abilityTypeFilter.value && abilityMyTypeOnly) {
                    abilityMyTypeOnly.checked = false;
                }
                populateAbilitySelect();
            });
            if (abilityMyTypeOnly) {
                abilityMyTypeOnly.addEventListener('change', function () {
                    // If checkbox is checked, clear the type dropdown
                    if (abilityMyTypeOnly.checked) {
                        abilityTypeFilter.value = '';
                    }
                    populateAbilitySelect();
                });
            }

            abilityCatalogSelect.addEventListener('change', function () {
                var sel = abilityCatalogSelect.options[abilityCatalogSelect.selectedIndex];
                abilityCatalogDesc.textContent = sel ? (sel.dataset.desc || '') : '';
            });

            // Submit Add Ability
            document.getElementById('btn-add-ability').addEventListener('click', function () {
                var activeTab = document.querySelector('#addAbilityModal .tab-pane.active');
                var body = {};

                if (activeTab.id === 'ability-tab-catalog') {
                    if (!abilityCatalogSelect.value) { alert('Select an ability.'); return; }
                    body.ability_id = parseInt(abilityCatalogSelect.value);
                } else {
                    var name = document.getElementById('custom-ability-name').value.trim();
                    if (!name) { alert('Enter a name.'); return; }
                    body.custom_name = name;
                    body.custom_desc = document.getElementById('custom-ability-desc').value.trim();
                    body.ability_kind = document.getElementById('custom-ability-kind').value;
                }

                postAction('add-ability', body, function (data) {
                    if (data.warning) {
                        alert(data.warning);
                    }
                    window.location.reload();
                });
            });
        }
    });
})();

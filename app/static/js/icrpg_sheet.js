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

        // ── HP adjustment ───────────────────────────────────────
        document.querySelectorAll('.icrpg-hp-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var delta = parseInt(btn.dataset.delta);
                postAction('hp', { delta: delta }, function (data) {
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
                });
            });
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
                    // Reload to refresh stat totals, defense, slot counts
                    window.location.reload();
                });
            });
        });
    });
})();

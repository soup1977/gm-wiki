/**
 * pin_entity.js — Pin/unpin entity buttons on detail pages.
 *
 * Looks for buttons with class "pin-entity-btn" and wires up AJAX
 * calls to /session-mode/pin and /session-mode/unpin.
 */
(function () {
    'use strict';

    var csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (!csrfMeta) return;
    var csrfToken = csrfMeta.getAttribute('content');

    document.querySelectorAll('.pin-entity-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var entityType = btn.dataset.entityType;
            var entityId   = parseInt(btn.dataset.entityId, 10);
            var isPinned   = btn.dataset.pinned === 'true';
            var url = isPinned ? '/session-mode/unpin' : '/session-mode/pin';

            btn.disabled = true;

            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({ entity_type: entityType, entity_id: entityId }),
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.ok) {
                    if (data.pinned) {
                        btn.dataset.pinned = 'true';
                        btn.classList.remove('btn-outline-info');
                        btn.classList.add('btn-info');
                        btn.innerHTML = '<i class="bi bi-pin-angle-fill"></i> Pinned';
                        btn.title = 'Unpin from session dashboard';
                    } else {
                        btn.dataset.pinned = 'false';
                        btn.classList.remove('btn-info');
                        btn.classList.add('btn-outline-info');
                        btn.innerHTML = '<i class="bi bi-pin-angle"></i> Pin';
                        btn.title = 'Pin to session dashboard';
                    }
                }
            })
            .catch(function () {
                btn.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Error';
            })
            .finally(function () {
                btn.disabled = false;
            });
        });
    });
})();

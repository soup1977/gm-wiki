/**
 * npc_flesh_out.js — "Flesh Out" AI button for NPC edit forms.
 *
 * Reads current form field values, sends them to /api/ai/flesh-out-npc,
 * and replaces the form fields with AI-enriched versions.
 *
 * Requires window.AI_STORY_ARC_ID to be set if adventure context should
 * be injected (optional — same pattern as ai_generate.js).
 */

(function () {
    'use strict';

    // -----------------------------------------------------------------------
    // Status messages shown while waiting for AI response
    // -----------------------------------------------------------------------
    const STATUS_MESSAGES = [
        { after: 0,  text: 'Reading NPC details...' },
        { after: 4,  text: 'Expanding and enriching...' },
        { after: 15, text: 'Still working — adding depth...' },
        { after: 30, text: 'Almost there — hang tight...' },
        { after: 60, text: 'Still processing — complex NPCs take longer...' },
    ];

    let elapsedTimer = null;

    // -----------------------------------------------------------------------
    // Inject the modal HTML once
    // -----------------------------------------------------------------------
    const modalHtml = `
    <div class="modal fade" id="npcFleshOutModal" tabindex="-1" aria-labelledby="npcFleshOutModalLabel" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content bg-dark border-secondary">
                <div class="modal-header border-secondary">
                    <h5 class="modal-title" id="npcFleshOutModalLabel">
                        <i class="bi bi-person-fill-gear"></i> Flesh Out NPC
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <p class="mb-2">
                        AI will read the current NPC fields and expand them into richer, more detailed versions —
                        adding personality quirks, vivid descriptions, secrets, and GM-usable hooks.
                    </p>
                    <p class="text-warning small mb-0">
                        <i class="bi bi-exclamation-triangle me-1"></i>
                        Current field values will be replaced. Make sure to save first if you want to keep them.
                    </p>
                    <div id="flesh-out-status" class="mt-3 d-none">
                        <span class="text-muted small">
                            <span class="spinner-border spinner-border-sm me-1"></span>
                            <span id="flesh-out-status-text">Reading NPC details...</span>
                            <span id="flesh-out-elapsed" class="ms-2 text-secondary">0:00</span>
                        </span>
                    </div>
                    <div id="flesh-out-error" class="mt-2 d-none"></div>
                </div>
                <div class="modal-footer border-secondary">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-warning" id="flesh-out-confirm-btn">
                        <i class="bi bi-person-fill-gear"></i> Flesh Out
                    </button>
                </div>
            </div>
        </div>
    </div>`;

    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    function getFormValue(name) {
        const el = document.querySelector(`[name="${name}"]`);
        if (!el) return '';
        return el.value || '';
    }

    function applyToForm(data) {
        const fieldMap = {
            name:                 'name',
            role:                 'role',
            status:               'status',
            faction:              'faction',
            physical_description: 'physical_description',
            personality:          'personality',
            secrets:              'secrets',
            notes:                'notes',
        };
        for (const [aiKey, formName] of Object.entries(fieldMap)) {
            if (data[aiKey] == null) continue;
            const el = document.querySelector(`[name="${formName}"]`);
            if (!el) continue;
            el.value = data[aiKey];
        }
    }

    function startTimer(startTime) {
        const statusEl = document.getElementById('flesh-out-status-text');
        const elapsedEl = document.getElementById('flesh-out-elapsed');

        elapsedTimer = setInterval(function () {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            if (elapsedEl) elapsedEl.textContent = mins + ':' + (secs < 10 ? '0' : '') + secs;
            if (statusEl) {
                for (let i = STATUS_MESSAGES.length - 1; i >= 0; i--) {
                    if (elapsed >= STATUS_MESSAGES[i].after) {
                        statusEl.textContent = STATUS_MESSAGES[i].text;
                        break;
                    }
                }
            }
        }, 1000);
    }

    function stopTimer() {
        if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
    }

    // -----------------------------------------------------------------------
    // Confirm button click — collect fields and send request
    // -----------------------------------------------------------------------

    document.getElementById('flesh-out-confirm-btn').addEventListener('click', function () {
        const btn = this;
        const statusDiv = document.getElementById('flesh-out-status');
        const errorDiv = document.getElementById('flesh-out-error');

        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Working…';
        statusDiv.classList.remove('d-none');
        errorDiv.classList.add('d-none');

        const payload = {
            name:                 getFormValue('name'),
            role:                 getFormValue('role'),
            status:               getFormValue('status'),
            faction:              getFormValue('faction'),
            physical_description: getFormValue('physical_description'),
            personality:          getFormValue('personality'),
            secrets:              getFormValue('secrets'),
            notes:                getFormValue('notes'),
        };

        if (window.AI_STORY_ARC_ID) {
            payload.story_arc_id = window.AI_STORY_ARC_ID;
        }

        const startTime = Date.now();
        startTimer(startTime);

        fetch('/api/ai/flesh-out-npc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        .then(r => r.json())
        .then(data => {
            stopTimer();
            if (data.error) {
                errorDiv.innerHTML = '<span class="text-danger"><i class="bi bi-x-circle me-1"></i>' +
                    data.error + '</span>';
                errorDiv.classList.remove('d-none');
                statusDiv.classList.add('d-none');
            } else {
                applyToForm(data);
                const modal = bootstrap.Modal.getInstance(document.getElementById('npcFleshOutModal'));
                modal.hide();
            }
        })
        .catch(err => {
            stopTimer();
            errorDiv.innerHTML = '<span class="text-danger">Request failed: ' + err.message + '</span>';
            errorDiv.classList.remove('d-none');
            statusDiv.classList.add('d-none');
        })
        .finally(() => {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-person-fill-gear"></i> Flesh Out';
        });
    });

    // Reset modal state when it closes
    document.getElementById('npcFleshOutModal').addEventListener('hidden.bs.modal', function () {
        stopTimer();
        document.getElementById('flesh-out-status').classList.add('d-none');
        document.getElementById('flesh-out-error').classList.add('d-none');
        document.getElementById('flesh-out-status-text').textContent = STATUS_MESSAGES[0].text;
        document.getElementById('flesh-out-elapsed').textContent = '0:00';
    });

})();

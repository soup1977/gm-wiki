/**
 * ai_generate.js
 * Generate Entry modal for entity create/edit forms.
 *
 * Usage: include this script on any form page that has a Generate Entry button.
 * The page must define window.AI_GENERATE_ENTITY_TYPE (e.g. "npc").
 *
 * Field mapping: the JSON keys returned by the AI endpoint must match
 * the HTML form input name attributes. If they don't, add a custom
 * mapping via window.SMART_FILL_FIELD_MAP = { aiKey: 'formFieldName' }.
 */

(function () {
    'use strict';

    // -----------------------------------------------------------------------
    // Status messages shown while waiting for AI response
    // -----------------------------------------------------------------------
    const STATUS_MESSAGES = [
        { after: 0,  text: 'Thinking...' },
        { after: 5,  text: 'Generating content...' },
        { after: 15, text: 'Still working — LLMs can take a minute...' },
        { after: 30, text: 'Almost there — hang tight...' },
        { after: 60, text: 'Still processing — complex entries take longer...' },
    ];

    let elapsedTimer = null;

    // -----------------------------------------------------------------------
    // Build and inject the modal HTML once
    // -----------------------------------------------------------------------
    const modalHtml = `
    <div class="modal fade" id="aiGenerateModal" tabindex="-1" aria-labelledby="aiGenerateModalLabel" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content bg-dark border-secondary">
                <div class="modal-header border-secondary">
                    <h5 class="modal-title" id="aiGenerateModalLabel">
                        <i class="bi bi-magic"></i> Generate Entry
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <p class="text-muted small mb-2">
                        Describe the concept and AI will generate a complete entry.
                        You can edit any field before saving.
                    </p>
                    <textarea id="ai-generate-prompt" class="form-control bg-dark border-secondary text-light"
                              rows="3" placeholder="e.g. A grizzled dwarven blacksmith who secretly works for the thieves' guild"></textarea>
                    <div id="ai-generate-status" class="text-muted small mt-2 d-none">
                        <span class="spinner-border spinner-border-sm me-1"></span>
                        <span id="ai-generate-status-text"></span>
                        <span id="ai-generate-elapsed" class="ms-2 text-secondary"></span>
                    </div>
                    <div id="ai-generate-error" class="alert alert-danger mt-2 d-none"></div>
                </div>
                <div class="modal-footer border-secondary">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="ai-generate-submit">
                        <i class="bi bi-magic"></i> Generate
                    </button>
                </div>
            </div>
        </div>
    </div>`;

    document.body.insertAdjacentHTML('beforeend', modalHtml);

    const modalEl = document.getElementById('aiGenerateModal');
    const promptInput = document.getElementById('ai-generate-prompt');
    const errorDiv = document.getElementById('ai-generate-error');
    const submitBtn = document.getElementById('ai-generate-submit');
    const statusDiv = document.getElementById('ai-generate-status');
    const statusText = document.getElementById('ai-generate-status-text');
    const elapsedSpan = document.getElementById('ai-generate-elapsed');

    // -----------------------------------------------------------------------
    // Submit handler
    // -----------------------------------------------------------------------
    submitBtn.addEventListener('click', function () {
        const concept = promptInput.value.trim();
        if (!concept) {
            showError('Please describe what you want to generate.');
            return;
        }

        const entityType = window.AI_GENERATE_ENTITY_TYPE || '';
        if (!entityType) {
            showError('Entity type not configured on this page.');
            return;
        }

        setLoading(true);
        clearError();
        startStatusUpdates();

        fetch('/api/ai/generate-entry', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ entity_type: entityType, prompt: concept }),
        })
            .then(r => r.json().then(data => ({ ok: r.ok, data })))
            .then(({ ok, data }) => {
                if (!ok || data.error) {
                    showError(data.error || 'An error occurred. Please try again.');
                    return;
                }
                applyToForm(data);
                bootstrap.Modal.getInstance(modalEl).hide();
            })
            .catch(() => {
                showError('Request failed — check your connection and try again.');
            })
            .finally(() => {
                setLoading(false);
                stopStatusUpdates();
            });
    });

    // Reset prompt and errors each time the modal opens
    modalEl.addEventListener('show.bs.modal', function () {
        promptInput.value = '';
        clearError();
        stopStatusUpdates();
    });

    // -----------------------------------------------------------------------
    // applyToForm — maps AI JSON keys to form input[name] attributes
    // -----------------------------------------------------------------------
    function applyToForm(data) {
        const fieldMap = window.SMART_FILL_FIELD_MAP || {};

        Object.entries(data).forEach(([key, value]) => {
            if (value === null || value === undefined) return;

            const formName = fieldMap[key] || key;
            const el = document.querySelector(`[name="${formName}"]`);
            if (!el) return;

            if (el.tagName === 'SELECT') {
                const opt = el.querySelector(`option[value="${value}"]`);
                if (opt) el.value = value;
            } else if (el.type === 'checkbox') {
                el.checked = Boolean(value);
            } else {
                el.value = value;
            }
        });
    }

    // -----------------------------------------------------------------------
    // Status message rotation + elapsed timer
    // -----------------------------------------------------------------------
    function startStatusUpdates() {
        const startTime = Date.now();
        statusDiv.classList.remove('d-none');
        statusText.textContent = STATUS_MESSAGES[0].text;
        elapsedSpan.textContent = '0:00';

        elapsedTimer = setInterval(function () {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            elapsedSpan.textContent = mins + ':' + (secs < 10 ? '0' : '') + secs;

            for (let i = STATUS_MESSAGES.length - 1; i >= 0; i--) {
                if (elapsed >= STATUS_MESSAGES[i].after) {
                    statusText.textContent = STATUS_MESSAGES[i].text;
                    break;
                }
            }
        }, 1000);
    }

    function stopStatusUpdates() {
        if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
        statusDiv.classList.add('d-none');
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------
    function setLoading(loading) {
        submitBtn.disabled = loading;
        submitBtn.innerHTML = loading
            ? '<span class="spinner-border spinner-border-sm me-1"></span> Generating…'
            : '<i class="bi bi-magic"></i> Generate';
    }

    function showError(msg) {
        errorDiv.textContent = msg;
        errorDiv.classList.remove('d-none');
    }

    function clearError() {
        errorDiv.textContent = '';
        errorDiv.classList.add('d-none');
    }

})();

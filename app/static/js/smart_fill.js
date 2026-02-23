/**
 * smart_fill.js
 * Shared Smart Fill modal for all entity create/edit forms.
 *
 * Usage: include this script on any form page that has a Smart Fill button.
 * The page must define window.SMART_FILL_ENTITY_TYPE (e.g. "npc").
 *
 * Field mapping: the JSON keys returned by the AI endpoint must match
 * the HTML form input name attributes. If they don't, add a custom
 * mapping via window.SMART_FILL_FIELD_MAP = { aiKey: 'formFieldName' }.
 */

(function () {
    'use strict';

    // -----------------------------------------------------------------------
    // Build and inject the modal HTML once
    // -----------------------------------------------------------------------
    const modalHtml = `
    <div class="modal fade" id="smartFillModal" tabindex="-1" aria-labelledby="smartFillModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-lg">
            <div class="modal-content bg-dark border-secondary">
                <div class="modal-header border-secondary">
                    <h5 class="modal-title" id="smartFillModalLabel">
                        <i class="bi bi-cpu"></i> Smart Fill from Notes
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <p class="text-muted small mb-2">
                        Paste any raw notes below — session notes, descriptions, anything.
                        Claude will read them and pre-fill the form fields. You can edit anything before saving.
                    </p>
                    <textarea id="smart-fill-text" class="form-control bg-dark border-secondary text-light font-monospace"
                              rows="10" placeholder="Paste your notes here…"></textarea>
                    <div id="smart-fill-error" class="alert alert-danger mt-2 d-none"></div>
                </div>
                <div class="modal-footer border-secondary">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="smart-fill-submit">
                        <i class="bi bi-stars"></i> Fill Fields
                    </button>
                </div>
            </div>
        </div>
    </div>`;

    document.body.insertAdjacentHTML('beforeend', modalHtml);

    const modalEl = document.getElementById('smartFillModal');
    const textArea = document.getElementById('smart-fill-text');
    const errorDiv = document.getElementById('smart-fill-error');
    const submitBtn = document.getElementById('smart-fill-submit');

    // -----------------------------------------------------------------------
    // Submit handler
    // -----------------------------------------------------------------------
    submitBtn.addEventListener('click', function () {
        const text = textArea.value.trim();
        if (!text) {
            showError('Please paste some notes first.');
            return;
        }

        const entityType = window.SMART_FILL_ENTITY_TYPE || '';
        if (!entityType) {
            showError('Entity type not configured on this page.');
            return;
        }

        setLoading(true);
        clearError();

        fetch('/api/ai/smart-fill', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ entity_type: entityType, text: text }),
        })
            .then(r => r.json().then(data => ({ ok: r.ok, data })))
            .then(({ ok, data }) => {
                if (!ok || data.error) {
                    showError(data.error || 'An error occurred. Please try again.');
                    return;
                }
                applyToForm(data);
                // Close modal on success
                bootstrap.Modal.getInstance(modalEl).hide();
            })
            .catch(() => {
                showError('Request failed — check your connection and try again.');
            })
            .finally(() => setLoading(false));
    });

    // Reset textarea and errors each time the modal opens
    modalEl.addEventListener('show.bs.modal', function () {
        textArea.value = '';
        clearError();
    });

    // -----------------------------------------------------------------------
    // applyToForm — maps AI JSON keys to form input[name] attributes
    // -----------------------------------------------------------------------
    function applyToForm(data) {
        const fieldMap = window.SMART_FILL_FIELD_MAP || {};

        Object.entries(data).forEach(([key, value]) => {
            if (value === null || value === undefined) return;

            // Allow custom mapping override
            const formName = fieldMap[key] || key;
            const el = document.querySelector(`[name="${formName}"]`);
            if (!el) return;

            if (el.tagName === 'SELECT') {
                // Only set if the value exists as an option
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
    // Helpers
    // -----------------------------------------------------------------------
    function setLoading(loading) {
        submitBtn.disabled = loading;
        submitBtn.innerHTML = loading
            ? '<span class="spinner-border spinner-border-sm me-1"></span> Filling…'
            : '<i class="bi bi-stars"></i> Fill Fields';
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

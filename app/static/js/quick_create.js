/**
 * quick_create.js
 * Reusable quick-create modal for stub entity creation from any form.
 *
 * Any button with class "quick-create-btn" and these data attributes will work:
 *   data-qc-entity  — entity type key (faction, npc, location, etc.)
 *   data-qc-target   — ID of the <select> to append the new option to
 *   data-qc-label    — Human label shown in modal title (e.g. "Faction")
 *
 * For encounter monster rows (no unique select ID), use:
 *   data-qc-target-mode="sibling" — finds nearest <select> via DOM traversal
 */

(function () {
    'use strict';

    // -----------------------------------------------------------------------
    // Inject the shared modal once
    // -----------------------------------------------------------------------
    const modalHtml = `
    <div class="modal fade" id="quickCreateModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content bg-dark border-secondary">
                <div class="modal-header border-secondary">
                    <h5 class="modal-title" id="quickCreateModalLabel">
                        <i class="bi bi-plus-circle"></i> Quick Create
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <label for="qc-name-input" class="form-label" id="qc-name-label">Name</label>
                    <input type="text" class="form-control" id="qc-name-input" autocomplete="off">
                    <div id="qc-error" class="text-danger small mt-2 d-none"></div>
                </div>
                <div class="modal-footer border-secondary">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="qc-submit-btn">
                        <span id="qc-submit-text">Create</span>
                        <span id="qc-spinner" class="spinner-border spinner-border-sm d-none" role="status"></span>
                    </button>
                </div>
            </div>
        </div>
    </div>`;

    document.body.insertAdjacentHTML('beforeend', modalHtml);

    const modal = new bootstrap.Modal(document.getElementById('quickCreateModal'));
    const nameInput = document.getElementById('qc-name-input');
    const errorDiv = document.getElementById('qc-error');
    const submitBtn = document.getElementById('qc-submit-btn');
    const submitText = document.getElementById('qc-submit-text');
    const spinner = document.getElementById('qc-spinner');
    const modalTitle = document.getElementById('quickCreateModalLabel');
    const nameLabel = document.getElementById('qc-name-label');

    // Track which button opened the modal
    let activeEntity = null;
    let activeTarget = null;
    let activeTargetMode = null;
    let activeTriggerBtn = null;

    // -----------------------------------------------------------------------
    // Event delegation: any .quick-create-btn click opens the modal
    // -----------------------------------------------------------------------
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.quick-create-btn');
        if (!btn) return;

        e.preventDefault();

        activeEntity = btn.dataset.qcEntity;
        activeTargetMode = btn.dataset.qcTargetMode || 'id';
        activeTriggerBtn = btn;

        if (activeTargetMode === 'id') {
            activeTarget = document.getElementById(btn.dataset.qcTarget);
        } else {
            // sibling mode: find nearest select in the same parent container
            activeTarget = btn.closest('.d-flex, .input-group, .mb-3, .row')?.querySelector('select');
        }

        const label = btn.dataset.qcLabel || 'Entity';
        modalTitle.innerHTML = `<i class="bi bi-plus-circle"></i> Quick Create ${label}`;

        // Session uses "title" not "name"
        nameLabel.textContent = activeEntity === 'session' ? 'Title' : 'Name';

        // Reset state
        nameInput.value = '';
        errorDiv.classList.add('d-none');
        errorDiv.textContent = '';
        submitBtn.disabled = false;
        submitText.textContent = 'Create';
        spinner.classList.add('d-none');

        modal.show();
    });

    // Auto-focus the input when modal opens
    document.getElementById('quickCreateModal').addEventListener('shown.bs.modal', function () {
        nameInput.focus();
    });

    // -----------------------------------------------------------------------
    // Submit: POST to API, update the target select
    // -----------------------------------------------------------------------
    function doSubmit() {
        const name = nameInput.value.trim();
        if (!name) {
            errorDiv.textContent = 'Name cannot be empty.';
            errorDiv.classList.remove('d-none');
            return;
        }

        submitBtn.disabled = true;
        submitText.textContent = 'Creating…';
        spinner.classList.remove('d-none');
        errorDiv.classList.add('d-none');

        fetch(`/api/quick-create/${activeEntity}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name }),
        })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    return { ok: resp.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok) {
                    errorDiv.textContent = result.data.error || 'Something went wrong.';
                    errorDiv.classList.remove('d-none');
                    submitBtn.disabled = false;
                    submitText.textContent = 'Create';
                    spinner.classList.add('d-none');
                    return;
                }

                var id = result.data.id;
                var displayName = result.data.name;

                if (activeTarget) {
                    // Check if option already exists (duplicate returned by API)
                    var exists = activeTarget.querySelector('option[value="' + id + '"]');
                    if (!exists) {
                        var opt = document.createElement('option');
                        opt.value = id;
                        opt.textContent = displayName;
                        activeTarget.appendChild(opt);
                    }

                    // Select the new option
                    if (activeTarget.multiple) {
                        // For multi-selects, add selection without clearing others
                        var targetOpt = activeTarget.querySelector('option[value="' + id + '"]');
                        if (targetOpt) targetOpt.selected = true;
                    } else {
                        activeTarget.value = String(id);
                    }
                }

                modal.hide();
            })
            .catch(function (err) {
                errorDiv.textContent = 'Network error. Please try again.';
                errorDiv.classList.remove('d-none');
                submitBtn.disabled = false;
                submitText.textContent = 'Create';
                spinner.classList.add('d-none');
            });
    }

    submitBtn.addEventListener('click', doSubmit);

    // Enter key submits
    nameInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            doSubmit();
        }
    });
})();

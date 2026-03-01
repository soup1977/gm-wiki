/**
 * entity_from_selection.js
 * Loaded only on Adventure Site detail and form pages.
 *
 * Lets the user select text → floating toolbar → quick modal → create NPC/Location/Quest/Item
 * In edit view (textarea): replaces the selected range with a shortcode.
 * In detail view (rendered HTML): POSTs to replace-text endpoint, then reloads.
 */
(function () {
    'use strict';

    // ── Config ──────────────────────────────────────────────────────────────────
    const TYPES = ['npc', 'location', 'quest', 'item'];

    const TYPE_LABELS = {
        npc:      'NPC',
        location: 'Location',
        quest:    'Quest',
        item:     'Item',
    };

    const DESC_LABELS = {
        npc:      'Role',
        location: 'Description',
        quest:    'Notes',
        item:     'Notes',
    };

    // Read site ID from data attribute set on the page container
    const container = document.getElementById('efs-context');
    const SITE_ID = container ? parseInt(container.dataset.siteId, 10) : null;
    const IS_EDIT = container ? container.dataset.mode === 'edit' : false;

    // ── State ────────────────────────────────────────────────────────────────────
    let savedStart = null;    // textarea selectionStart (edit view)
    let savedEnd   = null;    // textarea selectionEnd   (edit view)
    let savedText  = '';      // the selected text (both views)
    let activeType = 'npc';

    // ── Toolbar ──────────────────────────────────────────────────────────────────
    const toolbar = document.createElement('div');
    toolbar.id = 'efs-toolbar';
    toolbar.style.cssText = [
        'position:fixed',
        'z-index:9000',
        'display:none',
        'gap:4px',
        'padding:5px 8px',
        'background:#1e1e2e',
        'border:1px solid #444',
        'border-radius:6px',
        'box-shadow:0 4px 12px rgba(0,0,0,0.5)',
    ].join(';');

    TYPES.forEach(function (type) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-sm btn-outline-light py-0 px-2';
        btn.style.fontSize = '0.78rem';
        btn.textContent = TYPE_LABELS[type];
        btn.dataset.type = type;
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            openModal(type);
        });
        toolbar.appendChild(btn);
    });

    document.body.appendChild(toolbar);

    function showToolbar(x, y) {
        toolbar.style.display = 'flex';
        // Position above the selection; clamp to viewport
        const tw = toolbar.offsetWidth || 200;
        const left = Math.min(x, window.innerWidth - tw - 10);
        toolbar.style.left = Math.max(4, left) + 'px';
        toolbar.style.top  = (y - 44) + 'px';
    }

    function hideToolbar() {
        toolbar.style.display = 'none';
    }

    // ── Selection listeners ───────────────────────────────────────────────────────
    // Edit view: listen on the content textarea
    const textarea = document.getElementById('content');
    if (IS_EDIT && textarea) {
        textarea.addEventListener('mouseup', function (e) {
            const start = textarea.selectionStart;
            const end   = textarea.selectionEnd;
            if (start === end) { hideToolbar(); return; }
            savedStart = start;
            savedEnd   = end;
            savedText  = textarea.value.substring(start, end).trim();
            if (!savedText) { hideToolbar(); return; }
            showToolbar(e.clientX, e.clientY);
        });
    }

    // Detail view: listen on rendered content
    const siteContent = document.getElementById('site-content');
    if (!IS_EDIT && siteContent) {
        document.addEventListener('mouseup', function (e) {
            // Ignore clicks inside the toolbar itself
            if (toolbar.contains(e.target)) return;

            const sel = window.getSelection();
            const text = sel ? sel.toString().trim() : '';
            if (!text) { hideToolbar(); return; }

            // Only trigger if selection is within the site content
            if (!sel.rangeCount) { hideToolbar(); return; }
            const range = sel.getRangeAt(0);
            if (!siteContent.contains(range.commonAncestorContainer)) {
                hideToolbar();
                return;
            }

            savedText = text;
            const rect = range.getBoundingClientRect();
            showToolbar(rect.left + rect.width / 2, rect.top + window.scrollY);
            // Show at fixed position relative to viewport (toolbar is fixed)
            showToolbar(rect.left + rect.width / 2, rect.top);
        });
    }

    // Hide toolbar on scroll, Escape, or click outside
    document.addEventListener('scroll', hideToolbar, true);
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') hideToolbar();
    });
    document.addEventListener('mousedown', function (e) {
        if (!toolbar.contains(e.target)) hideToolbar();
    });

    // ── Modal ─────────────────────────────────────────────────────────────────────
    const modalHtml = `
<div class="modal fade" id="efsModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content bg-dark border-secondary text-light">
      <div class="modal-header border-secondary py-2">
        <h5 class="modal-title fs-6">Create Entity</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body pb-2">

        <!-- Type toggle -->
        <div class="btn-group w-100 mb-3" id="efs-type-group" role="group">
          <button type="button" class="btn btn-sm btn-outline-light" data-efs-type="npc">NPC</button>
          <button type="button" class="btn btn-sm btn-outline-light" data-efs-type="location">Location</button>
          <button type="button" class="btn btn-sm btn-outline-light" data-efs-type="quest">Quest</button>
          <button type="button" class="btn btn-sm btn-outline-light" data-efs-type="item">Item</button>
        </div>

        <!-- Name -->
        <div class="mb-3">
          <label for="efs-name" class="form-label form-label-sm">Name</label>
          <input type="text" class="form-control form-control-sm" id="efs-name">
        </div>

        <!-- Description (label changes by type) -->
        <div class="mb-2">
          <label for="efs-desc" class="form-label form-label-sm" id="efs-desc-label">Role</label>
          <input type="text" class="form-control form-control-sm" id="efs-desc" placeholder="Optional">
        </div>

        <!-- Error message -->
        <div class="alert alert-danger py-1 px-2 small mt-2 mb-0 d-none" id="efs-error"></div>
      </div>
      <div class="modal-footer border-secondary py-2 d-flex justify-content-between">
        <button type="button" class="btn btn-sm btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
        <div class="d-flex gap-2">
          <button type="button" class="btn btn-sm btn-outline-light" id="efs-just-create">Just Create</button>
          <button type="button" class="btn btn-sm btn-primary" id="efs-create-link">Create &amp; Link</button>
        </div>
      </div>
    </div>
  </div>
</div>`;

    document.body.insertAdjacentHTML('beforeend', modalHtml);

    const modalEl       = document.getElementById('efsModal');
    const bsModal       = new bootstrap.Modal(modalEl);
    const nameInput     = document.getElementById('efs-name');
    const descInput     = document.getElementById('efs-desc');
    const descLabel     = document.getElementById('efs-desc-label');
    const errorDiv      = document.getElementById('efs-error');
    const typeGroup     = document.getElementById('efs-type-group');
    const justCreateBtn = document.getElementById('efs-just-create');
    const createLinkBtn = document.getElementById('efs-create-link');

    function setActiveType(type) {
        activeType = type;
        typeGroup.querySelectorAll('[data-efs-type]').forEach(function (btn) {
            btn.classList.toggle('btn-light', btn.dataset.efsType === type);
            btn.classList.toggle('btn-outline-light', btn.dataset.efsType !== type);
        });
        descLabel.textContent = DESC_LABELS[type] || 'Notes';
    }

    typeGroup.addEventListener('click', function (e) {
        const btn = e.target.closest('[data-efs-type]');
        if (btn) setActiveType(btn.dataset.efsType);
    });

    function showError(msg) {
        errorDiv.textContent = msg;
        errorDiv.classList.remove('d-none');
    }

    function clearError() {
        errorDiv.classList.add('d-none');
        errorDiv.textContent = '';
    }

    function openModal(type) {
        hideToolbar();
        setActiveType(type);
        nameInput.value = savedText;
        descInput.value = '';
        clearError();
        bsModal.show();
        setTimeout(function () { nameInput.focus(); nameInput.select(); }, 300);
    }

    // ── API helpers ───────────────────────────────────────────────────────────────
    var csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    function apiCreate(type, name, description) {
        return fetch('/api/quick-create/' + type, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ name: name, description: description }),
        }).then(function (r) { return r.json().then(function (d) { return { status: r.status, data: d }; }); });
    }

    function apiReplaceText(find, replace) {
        if (!SITE_ID) return Promise.resolve({ status: 400, data: { error: 'No site ID' } });
        return fetch('/sites/' + SITE_ID + '/replace-text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ find: find, replace: replace }),
        }).then(function (r) { return r.json().then(function (d) { return { status: r.status, data: d }; }); });
    }

    // ── Toast ─────────────────────────────────────────────────────────────────────
    function showToast(msg, variant) {
        variant = variant || 'success';
        const toastHtml = `
<div class="toast align-items-center text-bg-${variant} border-0 mb-2"
     role="alert" aria-live="assertive" style="min-width:260px">
  <div class="d-flex">
    <div class="toast-body">${msg}</div>
    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
  </div>
</div>`;
        let container = document.getElementById('efs-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'efs-toast-container';
            container.style.cssText = 'position:fixed;bottom:1rem;right:1rem;z-index:9999;';
            document.body.appendChild(container);
        }
        container.insertAdjacentHTML('beforeend', toastHtml);
        const toastEl = container.lastElementChild;
        const t = new bootstrap.Toast(toastEl, { delay: 4000 });
        t.show();
        toastEl.addEventListener('hidden.bs.toast', function () { toastEl.remove(); });
    }

    // ── Button handlers ───────────────────────────────────────────────────────────
    justCreateBtn.addEventListener('click', function () {
        const name = nameInput.value.trim();
        const desc = descInput.value.trim();
        if (!name) { showError('Name is required.'); return; }
        clearError();
        justCreateBtn.disabled = true;
        createLinkBtn.disabled = true;

        apiCreate(activeType, name, desc).then(function (res) {
            justCreateBtn.disabled = false;
            createLinkBtn.disabled = false;
            if (res.status >= 400) {
                showError(res.data.error || 'Error creating entity.');
                return;
            }
            bsModal.hide();
            const sc = res.data.shortcode || ('#' + activeType + '[' + res.data.name + ']');
            showToast('Created <strong>' + res.data.name + '</strong>. Use: <code>' + sc + '</code>', 'success');
        }).catch(function () {
            justCreateBtn.disabled = false;
            createLinkBtn.disabled = false;
            showError('Network error. Please try again.');
        });
    });

    createLinkBtn.addEventListener('click', function () {
        const name = nameInput.value.trim();
        const desc = descInput.value.trim();
        if (!name) { showError('Name is required.'); return; }
        clearError();
        justCreateBtn.disabled = true;
        createLinkBtn.disabled = true;

        apiCreate(activeType, name, desc).then(function (res) {
            if (res.status >= 400) {
                justCreateBtn.disabled = false;
                createLinkBtn.disabled = false;
                showError(res.data.error || 'Error creating entity.');
                return;
            }
            const shortcode = res.data.shortcode || ('#' + activeType + '[' + res.data.name + ']');

            if (IS_EDIT && textarea) {
                // Replace in textarea
                bsModal.hide();
                const before = textarea.value.substring(0, savedStart);
                const after  = textarea.value.substring(savedEnd);
                textarea.value = before + shortcode + after;
                const newPos = savedStart + shortcode.length;
                textarea.selectionStart = newPos;
                textarea.selectionEnd   = newPos;
                textarea.dispatchEvent(new Event('input'));
                textarea.focus();
                showToast('Replaced with <code>' + shortcode + '</code>', 'success');
            } else {
                // Replace in stored content (detail view)
                apiReplaceText(savedText, shortcode).then(function (replaceRes) {
                    justCreateBtn.disabled = false;
                    createLinkBtn.disabled = false;
                    bsModal.hide();
                    if (replaceRes.status === 200) {
                        window.location.reload();
                    } else {
                        showToast(
                            'Created <strong>' + res.data.name + '</strong>. ' +
                            'Text not found exactly — use: <code>' + shortcode + '</code>',
                            'warning'
                        );
                    }
                }).catch(function () {
                    justCreateBtn.disabled = false;
                    createLinkBtn.disabled = false;
                    bsModal.hide();
                    showToast('Created. Use: <code>' + shortcode + '</code>', 'warning');
                });
            }
        }).catch(function () {
            justCreateBtn.disabled = false;
            createLinkBtn.disabled = false;
            showError('Network error. Please try again.');
        });
    });

})();

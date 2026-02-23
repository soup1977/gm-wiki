/**
 * bestiary_import.js
 * Handles the Open5e creature search and preview on the Bestiary import page.
 */

const searchInput = document.getElementById('search-input');
const resultsList = document.getElementById('results-list');
const previewPanel = document.getElementById('preview-panel');

let searchTimer = null;

// ---------------------------------------------------------------------------
// Search input — debounced 350ms
// ---------------------------------------------------------------------------
searchInput.addEventListener('input', function () {
    clearTimeout(searchTimer);
    const q = this.value.trim();
    if (q.length < 2) {
        resultsList.innerHTML = '<li class="list-group-item bg-transparent border-secondary text-muted small">Type at least 2 characters to search…</li>';
        return;
    }
    resultsList.innerHTML = '<li class="list-group-item bg-transparent border-secondary text-muted small"><span class="spinner-border spinner-border-sm me-2"></span>Searching…</li>';
    searchTimer = setTimeout(() => doSearch(q), 350);
});

// ---------------------------------------------------------------------------
// doSearch — fetches results list from our Flask proxy
// ---------------------------------------------------------------------------
function doSearch(q) {
    fetch('/bestiary/import/web/search?q=' + encodeURIComponent(q))
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                resultsList.innerHTML = `<li class="list-group-item bg-transparent border-danger text-danger small">${escHtml(data.error)}</li>`;
                return;
            }
            if (!Array.isArray(data) || data.length === 0) {
                resultsList.innerHTML = '<li class="list-group-item bg-transparent border-secondary text-muted small">No results found.</li>';
                return;
            }
            resultsList.innerHTML = data.map(r => `
                <li class="list-group-item list-group-item-action bg-dark border-secondary py-2"
                    data-slug="${escHtml(r.slug)}" role="button" style="cursor:pointer;">
                    <div class="d-flex justify-content-between align-items-center">
                        <strong class="text-light">${escHtml(r.name)}</strong>
                        <span class="text-muted small">${r.cr ? 'CR ' + escHtml(r.cr) : ''}</span>
                    </div>
                    <div class="text-muted small">${escHtml(r.size)} ${escHtml(r.type)}</div>
                </li>
            `).join('');

            // Attach click handlers
            resultsList.querySelectorAll('[data-slug]').forEach(item => {
                item.addEventListener('click', () => loadPreview(item.dataset.slug, item));
            });
        })
        .catch(() => {
            resultsList.innerHTML = '<li class="list-group-item bg-transparent border-danger text-danger small">Search failed — check your internet connection.</li>';
        });
}

// ---------------------------------------------------------------------------
// loadPreview — fetches full creature data and renders the preview panel
// ---------------------------------------------------------------------------
function loadPreview(slug, clickedItem) {
    // Highlight selected result
    resultsList.querySelectorAll('[data-slug]').forEach(el => {
        el.classList.remove('active');
    });
    if (clickedItem) clickedItem.classList.add('active');

    previewPanel.innerHTML = '<div class="text-center py-5"><span class="spinner-border"></span><p class="mt-2 text-muted">Loading…</p></div>';

    fetch('/bestiary/import/web/preview?slug=' + encodeURIComponent(slug))
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                previewPanel.innerHTML = `<div class="alert alert-danger">${escHtml(data.error)}</div>`;
                return;
            }

            // Build tag badges
            const tagBadges = data.tags
                ? data.tags.split(',').map(t => `<span class="badge bg-dark border border-secondary me-1">${escHtml(t)}</span>`).join('')
                : '';

            // Duplicate warning
            let dupAlert = '';
            let dupButtons = '';
            if (data.exists) {
                dupAlert = `
                    <div class="alert alert-warning py-2 mb-3">
                        <i class="bi bi-exclamation-triangle-fill me-1"></i>
                        <strong>"${escHtml(data.name)}"</strong> already exists in your Bestiary.
                    </div>`;
                dupButtons = `
                    <button type="button" class="btn btn-outline-warning btn-sm"
                        onclick="forceImport('${escHtml(slug)}')">
                        <i class="bi bi-download"></i> Import Anyway (Duplicate)
                    </button>`;
            }

            previewPanel.innerHTML = `
                <div class="d-flex justify-content-between align-items-start mb-3">
                    <div>
                        <h4 class="mb-1">${escHtml(data.name)}</h4>
                        <div class="text-muted small mb-1">
                            ${data.cr_level ? '<span class="me-3 fw-semibold">' + escHtml(data.cr_level) + '</span>' : ''}
                            ${data.type ? '<span class="badge bg-secondary me-1">' + escHtml(data.type) + '</span>' : ''}
                            ${data.size ? '<span class="badge bg-secondary me-1">' + escHtml(data.size) + '</span>' : ''}
                        </div>
                        ${tagBadges ? '<div class="mb-1">' + tagBadges + '</div>' : ''}
                        ${data.source ? '<div class="text-muted small">Source: ' + escHtml(data.source) + '</div>' : ''}
                    </div>
                </div>

                ${dupAlert}

                <div class="card bg-dark border-secondary mb-3" style="max-height: 50vh; overflow-y: auto;">
                    <div class="card-header small text-muted py-2">Stat Block Preview</div>
                    <div class="card-body stat-block-preview">${data.stat_block_html}</div>
                </div>

                <form method="post" action="/bestiary/import/web/save" id="import-form-${escHtml(slug)}">
                    <input type="hidden" name="slug" value="${escHtml(slug)}">
                    <input type="hidden" name="force" id="force-${escHtml(slug)}" value="">
                    <div class="d-flex gap-2 flex-wrap">
                        ${!data.exists ? `
                        <button type="submit" class="btn btn-success">
                            <i class="bi bi-download"></i> Import to Bestiary
                        </button>` : ''}
                        ${dupButtons}
                    </div>
                </form>
            `;
        })
        .catch(() => {
            previewPanel.innerHTML = '<div class="alert alert-danger">Failed to load preview. Please try again.</div>';
        });
}

// ---------------------------------------------------------------------------
// forceImport — sets the force flag and submits the import form
// ---------------------------------------------------------------------------
function forceImport(slug) {
    const forceInput = document.getElementById('force-' + slug);
    if (forceInput) {
        forceInput.value = '1';
        document.getElementById('import-form-' + slug).submit();
    }
}

// ---------------------------------------------------------------------------
// escHtml — minimal HTML escaping for dynamic content
// ---------------------------------------------------------------------------
function escHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

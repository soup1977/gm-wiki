/**
 * shortcode.js — Entity shortcode autocomplete panel
 *
 * Typing # in any textarea shows a floating panel where the user can
 * choose an entity type (NPC, Location, Item, Quest, Compendium) and
 * search for an existing entity or create a new one.
 *
 * On selection, inserts  #type[Name]  at the cursor position.
 * The server processes these on form save, replacing them with Markdown links.
 */
(function () {
  'use strict';

  // ── Type definitions ────────────────────────────────────────────────────────

  var TYPES = [
    { key: 'npc',   label: 'NPC',        icon: 'bi-person'       },
    { key: 'loc',   label: 'Location',   icon: 'bi-geo-alt'      },
    { key: 'item',  label: 'Item',       icon: 'bi-backpack'     },
    { key: 'quest', label: 'Quest',      icon: 'bi-flag'         },
    { key: 'comp',  label: 'Compendium', icon: 'bi-journal-text' },
    { key: 'pc',    label: 'PC',         icon: 'bi-person-badge' },
  ];

  // ── State ────────────────────────────────────────────────────────────────────

  var panel       = null;
  var activeTA    = null;  // the textarea that triggered the panel
  var searchTimer = null;
  var activeType  = null;  // currently selected type key

  // ── HTML escaping ────────────────────────────────────────────────────────────

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Panel creation ───────────────────────────────────────────────────────────

  function createPanel() {
    var el = document.createElement('div');
    el.id = 'shortcode-panel';
    el.style.cssText = [
      'position:absolute',
      'z-index:9999',
      'background:#2a2a3e',
      'border:1px solid #6c757d',
      'border-radius:6px',
      'box-shadow:0 4px 16px rgba(0,0,0,0.5)',
      'width:300px',
      'font-size:0.875rem',
      'color:#e0e0e0',
      'display:none',
    ].join(';');
    document.body.appendChild(el);
    return el;
  }

  // ── Positioning ──────────────────────────────────────────────────────────────

  function positionPanel(textarea) {
    var rect   = textarea.getBoundingClientRect();
    var scrollX = window.scrollX || window.pageXOffset;
    var scrollY = window.scrollY || window.pageYOffset;
    panel.style.left = (rect.left + scrollX) + 'px';
    panel.style.top  = (rect.bottom + scrollY + 4) + 'px';
  }

  // ── Show type-selection step ─────────────────────────────────────────────────

  function showTypeStep() {
    activeType = null;

    var html = '<div style="padding:8px 10px;border-bottom:1px solid #444;color:#aaa;font-size:0.8rem;">Link to entity — choose type:</div>';
    html += '<div style="display:flex;flex-wrap:wrap;gap:4px;padding:8px;">';
    TYPES.forEach(function (t) {
      html += '<button class="shortcode-type-btn" data-type="' + escHtml(t.key) + '" ' +
        'style="background:#3a3a5e;border:1px solid #555;border-radius:4px;' +
        'color:#e0e0e0;padding:4px 10px;cursor:pointer;font-size:0.8rem;">' +
        '<i class="bi ' + escHtml(t.icon) + ' me-1"></i>' + escHtml(t.label) +
        '</button>';
    });
    html += '</div>';

    panel.innerHTML = html;
    panel.style.display = 'block';

    // Type button clicks
    panel.querySelectorAll('.shortcode-type-btn').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        showSearchStep(btn.dataset.type);
      });
    });
  }

  // ── Show name-search step ────────────────────────────────────────────────────

  function showSearchStep(typeKey) {
    activeType = typeKey;
    var typeCfg = TYPES.find(function (t) { return t.key === typeKey; });
    var typeLabel = typeCfg ? typeCfg.label : typeKey;

    var html =
      '<div style="padding:6px 10px;border-bottom:1px solid #444;display:flex;align-items:center;gap:6px;">' +
        '<button class="shortcode-back-btn" style="background:none;border:none;color:#aaa;cursor:pointer;padding:0;font-size:1rem;" title="Back">&#8592;</button>' +
        '<span style="color:#aaa;font-size:0.8rem;">Link ' + escHtml(typeLabel) + ':</span>' +
      '</div>' +
      '<div style="padding:6px 8px;border-bottom:1px solid #444;">' +
        '<input id="shortcode-search-input" type="text" placeholder="Type a name..." ' +
          'style="width:100%;background:#1a1a2e;border:1px solid #555;border-radius:4px;' +
          'color:#e0e0e0;padding:4px 8px;font-size:0.875rem;" autocomplete="off">' +
      '</div>' +
      '<div id="shortcode-results" style="max-height:200px;overflow-y:auto;"></div>';

    panel.innerHTML = html;

    var input = panel.querySelector('#shortcode-search-input');
    input.focus();

    // Render initial empty-query results
    fetchResults('', typeKey);

    // Debounced search on input
    input.addEventListener('input', function () {
      clearTimeout(searchTimer);
      var q = input.value;
      searchTimer = setTimeout(function () {
        fetchResults(q, typeKey);
      }, 300);
    });

    // Back button
    panel.querySelector('.shortcode-back-btn').addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      showTypeStep();
    });

    // Keyboard nav: Escape = close, Enter = pick first result
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { closePanel(); }
      if (e.key === 'Enter') {
        e.preventDefault();
        var first = panel.querySelector('.shortcode-result-btn');
        if (first) first.click();
      }
    });
  }

  // ── Fetch matching entities ──────────────────────────────────────────────────

  function fetchResults(q, typeKey) {
    var url = '/api/entity-search?type=' + encodeURIComponent(typeKey) +
              '&q=' + encodeURIComponent(q);
    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) { renderResults(data, q, typeKey); })
      .catch(function () { renderResults([], q, typeKey); });
  }

  function renderResults(entities, q, typeKey) {
    var container = panel.querySelector('#shortcode-results');
    if (!container) return;

    var html = '';
    var trimmed = q.trim();

    // "Create new" option — always shown if the user has typed something
    if (typeKey !== 'pc' && trimmed) {
      html +=
        '<button class="shortcode-result-btn" data-name="' + escHtml(trimmed) + '" ' +
        'data-create="1" ' +
        'style="width:100%;text-align:left;background:none;border:none;border-bottom:1px solid #333;' +
        'color:#7ec8e3;padding:7px 12px;cursor:pointer;">' +
        '<i class="bi bi-plus-circle me-1"></i> Create new &ldquo;' + escHtml(trimmed) + '&rdquo;' +
        '</button>';
    }

    // Existing matches
    entities.forEach(function (e) {
      html +=
        '<button class="shortcode-result-btn" data-name="' + escHtml(e.name) + '" ' +
        'style="width:100%;text-align:left;background:none;border:none;border-bottom:1px solid #333;' +
        'color:#e0e0e0;padding:7px 12px;cursor:pointer;">' +
        '<i class="bi bi-link me-1 text-muted"></i>' + escHtml(e.name) +
        '</button>';
    });

    if (!html) {
      html = '<p style="color:#888;padding:8px 12px;margin:0;font-size:0.8rem;">No matches found.</p>';
    }

    container.innerHTML = html;

    // Result button clicks
    container.querySelectorAll('.shortcode-result-btn').forEach(function (btn) {
      btn.addEventListener('mouseenter', function () {
        btn.style.background = '#3a3a5e';
      });
      btn.addEventListener('mouseleave', function () {
        btn.style.background = 'none';
      });
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        insertShortcode(typeKey, btn.dataset.name);
      });
    });
  }

  // ── Insert shortcode into textarea ──────────────────────────────────────────

  function insertShortcode(typeKey, name) {
    if (!activeTA) return;
    var shortcode = '#' + typeKey + '[' + name + ']';
    var start = activeTA.selectionStart;
    // Remove the '#' character that triggered the panel (it's at start - 1)
    var before = activeTA.value.substring(0, start - 1);
    var after  = activeTA.value.substring(start);
    activeTA.value = before + shortcode + after;
    var cursor = before.length + shortcode.length;
    activeTA.selectionStart = activeTA.selectionEnd = cursor;
    activeTA.focus();
    // Trigger change event so any listeners (e.g. autoresize) update
    activeTA.dispatchEvent(new Event('input', { bubbles: true }));
    closePanel();
  }

  // ── Open / close ─────────────────────────────────────────────────────────────

  function openPanel(textarea) {
    activeTA = textarea;
    positionPanel(textarea);
    showTypeStep();
  }

  function closePanel() {
    if (panel) {
      panel.style.display = 'none';
      panel.innerHTML = '';
    }
    activeTA = null;
    activeType = null;
    clearTimeout(searchTimer);
  }

  // ── Event wiring ─────────────────────────────────────────────────────────────

  function attachToTextareas() {
    document.querySelectorAll('form textarea').forEach(function (ta) {
      if (ta.dataset.shortcodeAttached) return;
      ta.dataset.shortcodeAttached = '1';

      ta.addEventListener('input', function (e) {
        var val = ta.value;
        var pos = ta.selectionStart;
        // Detect a bare '#' just typed (the char immediately before cursor)
        if (pos > 0 && val.charAt(pos - 1) === '#') {
          // Make sure it's not already part of an existing shortcode
          var before = val.substring(0, pos - 1);
          // Only trigger if the character before '#' is whitespace, start-of-string,
          // or a newline — not in the middle of a word.
          var prevChar = before.length > 0 ? before.charAt(before.length - 1) : '';
          if (prevChar === '' || /[\s\n\r]/.test(prevChar)) {
            openPanel(ta);
          }
        }
      });
    });
  }

  // Close panel when clicking outside it
  document.addEventListener('click', function (e) {
    if (panel && panel.style.display !== 'none' && !panel.contains(e.target)) {
      closePanel();
    }
  });

  // Close panel on Escape from anywhere
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && panel && panel.style.display !== 'none') {
      closePanel();
    }
  });

  // ── Init ─────────────────────────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', function () {
    panel = createPanel();
    attachToTextareas();

    // Re-attach if dynamic textareas appear (future-proofing)
    var observer = new MutationObserver(function () {
      attachToTextareas();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  });

}());

/**
 * Global Search — debounced typeahead search across all entity types.
 *
 * Looks for #global-search-input and #global-search-results in the DOM.
 * Optionally reads data-search-mode="player_wiki" from the input to
 * restrict results to player-visible entities only.
 */
(function () {
  'use strict';

  const input = document.getElementById('global-search-input');
  const dropdown = document.getElementById('global-search-results');
  if (!input || !dropdown) return;

  const mode = input.dataset.searchMode || 'gm';
  const campaignId = input.dataset.campaignId || '';
  let debounceTimer = null;
  let activeIndex = -1;
  let currentResults = [];

  // ── Debounced fetch ──────────────────────────────────────────────
  input.addEventListener('input', function () {
    clearTimeout(debounceTimer);
    const q = input.value.trim();
    if (q.length < 2) { hideDropdown(); return; }
    debounceTimer = setTimeout(function () { doSearch(q); }, 300);
  });

  // ── Keyboard navigation ──────────────────────────────────────────
  input.addEventListener('keydown', function (e) {
    if (!dropdown.classList.contains('show')) return;
    const items = dropdown.querySelectorAll('.gs-result');
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIndex = Math.min(activeIndex + 1, items.length - 1);
      highlightItem(items);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
      highlightItem(items);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIndex >= 0 && items[activeIndex]) {
        window.location.href = items[activeIndex].dataset.url;
      }
    } else if (e.key === 'Escape') {
      hideDropdown();
      input.blur();
    }
  });

  // Close dropdown when clicking outside
  document.addEventListener('click', function (e) {
    if (!input.contains(e.target) && !dropdown.contains(e.target)) {
      hideDropdown();
    }
  });

  // ── Search request ───────────────────────────────────────────────
  function doSearch(q) {
    var url = '/api/global-search?q=' + encodeURIComponent(q) + '&mode=' + mode;
    if (campaignId) url += '&campaign_id=' + campaignId;
    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        currentResults = [];
        renderResults(data);
      })
      .catch(function () { hideDropdown(); });
  }

  // ── Render grouped results ─────────────────────────────────────
  function renderResults(data) {
    dropdown.innerHTML = '';
    activeIndex = -1;

    var groups = data.groups || [];

    if (groups.length === 0) {
      dropdown.innerHTML = '<div class="dropdown-item text-muted small">No results found</div>';
      dropdown.classList.add('show');
      return;
    }

    var allResults = [];

    groups.forEach(function (group) {
      // Group header
      var header = document.createElement('div');
      header.className = 'dropdown-header d-flex align-items-center gap-2 text-muted small py-1';
      header.innerHTML = '<i class="bi ' + group.icon + '"></i> ' + group.label +
          ' <span class="badge bg-secondary ms-auto">' + group.results.length + '</span>';
      dropdown.appendChild(header);

      // Results in this group
      group.results.forEach(function (item) {
        var globalIdx = allResults.length;
        allResults.push(item);

        var el = document.createElement('a');
        el.className = 'dropdown-item gs-result d-flex align-items-center gap-2 ps-4';
        el.href = item.url;
        el.dataset.url = item.url;
        el.dataset.index = globalIdx;

        // Name
        var nameSpan = document.createElement('span');
        nameSpan.className = 'flex-grow-1 text-truncate';
        nameSpan.textContent = item.name;
        el.appendChild(nameSpan);

        // Subtitle
        if (item.subtitle) {
          var sub = document.createElement('small');
          sub.className = 'text-muted';
          sub.textContent = item.subtitle;
          el.appendChild(sub);
        }

        el.addEventListener('mouseenter', function () {
          activeIndex = globalIdx;
          highlightItem(dropdown.querySelectorAll('.gs-result'));
        });

        dropdown.appendChild(el);
      });
    });

    currentResults = allResults;
    dropdown.classList.add('show');
  }

  // ── Helpers ──────────────────────────────────────────────────────
  function highlightItem(items) {
    items.forEach(function (el, i) {
      el.classList.toggle('active', i === activeIndex);
    });
  }

  function hideDropdown() {
    dropdown.classList.remove('show');
    dropdown.innerHTML = '';
    activeIndex = -1;
    currentResults = [];
  }
})();

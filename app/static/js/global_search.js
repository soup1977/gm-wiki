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
        currentResults = data;
        renderResults(data);
      })
      .catch(function () { hideDropdown(); });
  }

  // ── Render results ───────────────────────────────────────────────
  function renderResults(items) {
    dropdown.innerHTML = '';
    activeIndex = -1;

    if (items.length === 0) {
      dropdown.innerHTML = '<div class="dropdown-item text-muted small">No results found</div>';
      dropdown.classList.add('show');
      return;
    }

    items.forEach(function (item, idx) {
      var el = document.createElement('a');
      el.className = 'dropdown-item gs-result d-flex align-items-center gap-2';
      el.href = item.url;
      el.dataset.url = item.url;
      el.dataset.index = idx;

      // Icon
      var icon = document.createElement('i');
      icon.className = 'bi ' + item.icon + ' text-muted';
      el.appendChild(icon);

      // Name
      var nameSpan = document.createElement('span');
      nameSpan.className = 'flex-grow-1 text-truncate';
      nameSpan.textContent = item.name;
      el.appendChild(nameSpan);

      // Subtitle / type badge
      if (item.subtitle) {
        var sub = document.createElement('small');
        sub.className = 'text-muted';
        sub.textContent = item.subtitle;
        el.appendChild(sub);
      } else {
        var badge = document.createElement('span');
        badge.className = 'badge bg-secondary';
        badge.textContent = item.type;
        el.appendChild(badge);
      }

      el.addEventListener('mouseenter', function () {
        activeIndex = idx;
        highlightItem(dropdown.querySelectorAll('.gs-result'));
      });

      dropdown.appendChild(el);
    });

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

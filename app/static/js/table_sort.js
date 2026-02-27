/**
 * table_sort.js — Reusable client-side table sorting for GM Wiki
 *
 * Usage:
 *   Add data-sortable="true" to any <table> element.
 *   Add data-sort="text|number|date" to any <th> you want to be sortable.
 *
 * Grouped tables (collapsible):
 *   Give each group's data <tbody> the class "group-rows".
 *   The sorter will sort rows within each group-rows tbody independently,
 *   leaving the header tbody elements (which hold the toggle rows) untouched.
 *
 * Flat tables:
 *   A single plain <tbody> — all rows sorted together.
 */

(function () {
  'use strict';

  const ICON_NEUTRAL = ' <span class="sort-icon text-muted small">⇅</span>';
  const ICON_ASC     = ' <span class="sort-icon text-primary small">▲</span>';
  const ICON_DESC    = ' <span class="sort-icon text-primary small">▼</span>';

  /** Return the plain text value of a cell, trimmed. */
  function cellText(row, colIndex) {
    const cell = row.cells[colIndex];
    return cell ? cell.innerText.trim() : '';
  }

  /** Compare function for a given sort type and direction. */
  function getComparer(sortType, colIndex, direction) {
    return function (a, b) {
      const aVal = cellText(a, colIndex);
      const bVal = cellText(b, colIndex);
      let result = 0;

      if (sortType === 'number') {
        result = (parseFloat(aVal) || 0) - (parseFloat(bVal) || 0);
      } else if (sortType === 'date') {
        result = new Date(aVal || 0) - new Date(bVal || 0);
      } else {
        // text — locale-aware, case-insensitive
        result = aVal.localeCompare(bVal, undefined, { sensitivity: 'base' });
      }

      return direction === 'asc' ? result : -result;
    };
  }

  /**
   * Sort a table by a given column.
   *
   * If the table has any <tbody class="group-rows"> elements (grouped mode),
   * rows are sorted within each group independently.
   *
   * Otherwise all rows in the single <tbody> are sorted together.
   */
  function sortTable(table, colIndex, sortType, direction) {
    const comparer = getComparer(sortType, colIndex, direction);
    const groupBodies = table.querySelectorAll('tbody.group-rows');

    if (groupBodies.length > 0) {
      // Grouped mode — sort within each group body independently
      groupBodies.forEach(function (tbody) {
        const rows = Array.from(tbody.rows);
        rows.sort(comparer);
        rows.forEach(function (r) { tbody.appendChild(r); });
      });
    } else {
      // Flat mode — sort all rows in the single tbody
      const tbody = table.querySelector('tbody');
      if (!tbody) return;
      const rows = Array.from(tbody.rows);
      rows.sort(comparer);
      rows.forEach(function (r) { tbody.appendChild(r); });
    }
  }

  /** Update all header icons; highlight the active sort column. */
  function updateHeaders(table, activeIndex, direction) {
    table.querySelectorAll('thead th[data-sort]').forEach(function (th) {
      // Strip any existing sort icon
      th.innerHTML = th.innerHTML.replace(/<span class="sort-icon[^"]*"[^>]*>.*?<\/span>/g, '');

      const thColIndex = Array.from(th.parentElement.cells).indexOf(th);
      if (thColIndex === activeIndex) {
        th.innerHTML += (direction === 'asc' ? ICON_ASC : ICON_DESC);
      } else {
        th.innerHTML += ICON_NEUTRAL;
      }
    });
  }

  /** Initialise a single sortable table. */
  function initTable(table) {
    const headers = table.querySelectorAll('thead th[data-sort]');

    headers.forEach(function (th) {
      th.style.cursor = 'pointer';
      th.style.userSelect = 'none';
      th.innerHTML += ICON_NEUTRAL;
      th.dataset.sortDir = 'none';

      th.addEventListener('click', function () {
        const colIndex = Array.from(th.parentElement.cells).indexOf(th);
        const sortType = th.dataset.sort || 'text';

        const prev = th.dataset.sortDir;
        const direction = (prev === 'asc') ? 'desc' : 'asc';

        headers.forEach(function (h) { h.dataset.sortDir = 'none'; });
        th.dataset.sortDir = direction;

        sortTable(table, colIndex, sortType, direction);
        updateHeaders(table, colIndex, direction);
      });
    });
  }

  function init() {
    document.querySelectorAll('table[data-sortable="true"]').forEach(initTable);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

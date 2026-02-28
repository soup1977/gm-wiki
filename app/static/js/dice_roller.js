/**
 * Dice Roller — pure client-side dice rolling with history.
 *
 * Supports expressions like: d20, 2d6, 2d6+3, 4d8-1, d100
 * History stored in sessionStorage so it persists across page navigation.
 */
(function () {
  'use strict';

  var form = document.getElementById('dice-custom-form');
  var input = document.getElementById('dice-custom-input');
  var historyEl = document.getElementById('dice-history');
  var clearBtn = document.getElementById('dice-clear-history');
  if (!form || !historyEl) return;

  var STORAGE_KEY = 'gmwiki_dice_history';
  var MAX_HISTORY = 20;

  // ── Get current roll mode (normal / advantage / disadvantage) ─────
  function getRollMode() {
    var checked = document.querySelector('input[name="dice-mode"]:checked');
    return checked ? checked.value : 'normal';
  }

  // ── Parse a dice expression like "2d6+3" ──────────────────────────
  function parseDiceExpr(str) {
    str = str.replace(/\s/g, '').toLowerCase();
    var match = str.match(/^(\d*)d(\d+)([+-]\d+)?$/);
    if (!match) return null;
    return {
      count: parseInt(match[1] || '1', 10),
      sides: parseInt(match[2], 10),
      modifier: parseInt(match[3] || '0', 10)
    };
  }

  // ── Roll a single set of dice from a parsed object ────────────────
  function rollOnce(parsed) {
    var rolls = [];
    for (var i = 0; i < parsed.count; i++) {
      rolls.push(Math.floor(Math.random() * parsed.sides) + 1);
    }
    var sum = rolls.reduce(function (a, b) { return a + b; }, 0);
    return { rolls: rolls, total: sum + parsed.modifier };
  }

  // ── Roll dice with advantage/disadvantage support ─────────────────
  function rollDice(expr) {
    var parsed = parseDiceExpr(expr);
    if (!parsed || parsed.count < 1 || parsed.count > 100 || parsed.sides < 1) return null;

    var mode = getRollMode();

    if (mode === 'normal') {
      var r = rollOnce(parsed);
      return {
        expression: expr,
        rolls: r.rolls,
        modifier: parsed.modifier,
        total: r.total
      };
    }

    // Roll twice for advantage/disadvantage
    var r1 = rollOnce(parsed);
    var r2 = rollOnce(parsed);
    var picked = (mode === 'advantage')
      ? (r1.total >= r2.total ? r1 : r2)
      : (r1.total <= r2.total ? r1 : r2);
    var dropped = (picked === r1) ? r2 : r1;

    return {
      expression: expr,
      rolls: picked.rolls,
      modifier: parsed.modifier,
      total: picked.total,
      mode: mode,
      droppedRolls: dropped.rolls,
      droppedTotal: dropped.total
    };
  }

  // ── History management ────────────────────────────────────────────
  function getHistory() {
    try {
      return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]');
    } catch (e) { return []; }
  }

  function saveHistory(history) {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(0, MAX_HISTORY)));
  }

  function addToHistory(result) {
    var history = getHistory();
    history.unshift(result);
    saveHistory(history);
    renderHistory();
  }

  function renderHistory() {
    var history = getHistory();
    historyEl.innerHTML = '';

    if (history.length === 0) {
      historyEl.innerHTML = '<div class="text-muted small text-center">No rolls yet</div>';
      return;
    }

    history.forEach(function (r, idx) {
      var item = document.createElement('div');
      item.className = 'border-bottom border-secondary py-2' + (idx === 0 ? ' bg-secondary bg-opacity-25 px-2 rounded' : ' px-2');

      var header = document.createElement('div');
      header.className = 'd-flex justify-content-between align-items-center';

      var leftSide = document.createElement('span');
      leftSide.className = 'fw-semibold';
      leftSide.textContent = r.expression;
      // Show mode badge
      if (r.mode) {
        var badge = document.createElement('span');
        badge.className = 'badge ms-1 ' + (r.mode === 'advantage' ? 'bg-success' : 'bg-danger');
        badge.textContent = r.mode === 'advantage' ? 'ADV' : 'DIS';
        leftSide.appendChild(badge);
      }
      header.appendChild(leftSide);

      var totalSpan = document.createElement('span');
      totalSpan.className = 'fs-5 fw-bold' + (idx === 0 ? ' text-warning' : ' text-light');
      totalSpan.textContent = r.total;
      header.appendChild(totalSpan);

      item.appendChild(header);

      // Show both rolls for advantage/disadvantage
      if (r.mode && r.droppedRolls) {
        var formatRoll = function(rolls, mod, total) {
          var s = '[' + rolls.join(', ') + ']';
          if (mod !== 0) s += (mod > 0 ? ' + ' : ' - ') + Math.abs(mod);
          s += ' = ' + total;
          return s;
        };

        var kept = document.createElement('small');
        kept.className = 'd-block ' + (r.mode === 'advantage' ? 'text-success' : 'text-danger');
        kept.innerHTML = '<i class="bi bi-check-circle me-1"></i>' + formatRoll(r.rolls, r.modifier, r.total);
        item.appendChild(kept);

        var dropped = document.createElement('small');
        dropped.className = 'text-muted d-block';
        dropped.style.opacity = '0.5';
        dropped.innerHTML = '<i class="bi bi-x-circle me-1"></i>' + formatRoll(r.droppedRolls, r.modifier, r.droppedTotal);
        item.appendChild(dropped);
      }
      // Show individual dice values for normal rolls with multiple dice or modifier
      else if (r.rolls.length > 1 || r.modifier !== 0) {
        var detail = document.createElement('small');
        detail.className = 'text-muted';
        var parts = '[' + r.rolls.join(', ') + ']';
        if (r.modifier !== 0) {
          parts += (r.modifier > 0 ? ' + ' : ' - ') + Math.abs(r.modifier);
        }
        detail.textContent = parts;
        item.appendChild(detail);
      }

      historyEl.appendChild(item);
    });
  }

  // ── Quick-roll buttons ────────────────────────────────────────────
  document.querySelectorAll('[data-dice]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var expr = btn.dataset.dice;
      var result = rollDice(expr);
      if (result) addToHistory(result);
    });
  });

  // ── Custom expression form ────────────────────────────────────────
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var expr = input.value.trim();
    if (!expr) return;
    var result = rollDice(expr);
    if (result) {
      addToHistory(result);
      input.value = '';
    } else {
      input.classList.add('is-invalid');
      setTimeout(function () { input.classList.remove('is-invalid'); }, 1500);
    }
  });

  // ── Clear history ─────────────────────────────────────────────────
  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      sessionStorage.removeItem(STORAGE_KEY);
      renderHistory();
    });
  }

  // ── Initial render ────────────────────────────────────────────────
  renderHistory();
})();

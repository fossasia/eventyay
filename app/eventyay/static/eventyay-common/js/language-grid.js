/**
 * Language Grid Widget
 *
 * Initialises every `.language-grid-widget` container on the page:
 *  - Toggle expand / collapse via the summary bar
 *  - Live search filtering of language cells
 *  - Selected-checkbox ↔ badge synchronisation
 *  - Deselect-all toolbar button

 */

(function () {
  'use strict';

  var MAX_VISIBLE_BADGES = 8;

  function initLanguageGrid(widget) {
    if (widget.dataset.languageGridInit === 'true') return;

    var summary = widget.querySelector('[data-language-grid-summary]');
    var panel = widget.querySelector('[data-language-grid-panel]');
    var searchInput = widget.querySelector('[data-language-grid-search]');
    var grid = widget.querySelector('[data-language-grid-grid]');
    var badgesContainer = widget.querySelector('[data-language-grid-badges]');
    var countLabel = widget.querySelector('[data-language-grid-count]');
    var noResults = widget.querySelector('[data-language-grid-no-results]');
    var deselectAllBtn = widget.querySelector('[data-language-grid-deselect-all]');


    if (!summary || !panel || !grid) return;
    widget.dataset.languageGridInit = 'true';
    widget.classList.add('is-ready');
    panel.hidden = true;

    var emptyText = (countLabel && countLabel.getAttribute('data-empty-text')) || (countLabel ? countLabel.textContent.trim() : '');
    var selectedSingularText = (countLabel && countLabel.getAttribute('data-selected-singular-text')) || '';
    var selectedPluralText = (countLabel && countLabel.getAttribute('data-selected-plural-text')) || selectedSingularText;
    var overflowText = (countLabel && countLabel.getAttribute('data-overflow-text')) || '';

    var cells = [];
    var checkboxes = [];
    var cellNodes = grid.querySelectorAll('[data-language-grid-cell]');
    for (var i = 0; i < cellNodes.length; i++) {
      cells.push(cellNodes[i]);
      checkboxes.push(cellNodes[i].querySelector('input[type="checkbox"]'));
    }

    // -- Toggle expand / collapse --
    summary.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      var isExpanded = widget.classList.toggle('is-expanded');
      summary.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
      panel.hidden = !isExpanded;
      if (isExpanded && searchInput) {
        setTimeout(function () { searchInput.focus(); }, 50);
      }
    });

    // -- Keyboard accessibility: Enter/Space toggles --
    summary.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        summary.click();
      }
    });

    // -- Search filtering --
    if (searchInput) {
      searchInput.addEventListener('input', function () {
        var query = searchInput.value.trim().toLowerCase();
        var visibleCount = 0;

        for (var j = 0; j < cells.length; j++) {
          var label = (cells[j].getAttribute('data-language-name') || '').toLowerCase();
          var code = (checkboxes[j] && checkboxes[j].value || '').toLowerCase();
          var matches = !query || label.indexOf(query) !== -1 || code.indexOf(query) !== -1;
          if (matches) {
            cells[j].classList.remove('is-hidden');
            visibleCount++;
          } else {
            cells[j].classList.add('is-hidden');
          }
        }

        if (noResults) {
          noResults.classList.toggle('is-visible', visibleCount === 0);
        }
      });

      // Prevent form submission when pressing Enter in the search box
      searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') e.preventDefault();
      });
    }

    // -- Sync badges + cell highlight --
    function syncBadges() {
      if (!badgesContainer) return;
      badgesContainer.innerHTML = '';

      var selected = [];
      for (var j = 0; j < cells.length; j++) {
        var cb = checkboxes[j];
        if (!cb) continue;
        if (cb.checked) {
          cells[j].classList.add('is-checked');
          selected.push({
            code: cb.value,
            name: cells[j].getAttribute('data-language-name') || cb.value
          });
        } else {
          cells[j].classList.remove('is-checked');
        }
      }

      var shown = selected.slice(0, MAX_VISIBLE_BADGES);
      for (var k = 0; k < shown.length; k++) {
        var badge = document.createElement('span');
        badge.className = 'language-grid-badge';
        badge.textContent = shown[k].name;
        badgesContainer.appendChild(badge);
      }

      if (selected.length > MAX_VISIBLE_BADGES) {
        var overflow = document.createElement('span');
        overflow.className = 'language-grid-badge-overflow';
        overflow.textContent = '+' + (selected.length - MAX_VISIBLE_BADGES) + (overflowText ? ' ' + overflowText : '');
        badgesContainer.appendChild(overflow);
      }

      if (countLabel) {
        if (selected.length === 0) {
          countLabel.textContent = emptyText;
        } else {
          var selectedText = selected.length === 1 ? selectedSingularText : selectedPluralText;
          countLabel.textContent = selected.length + (selectedText ? ' ' + selectedText : '');
        }
      }
    }

    function dispatchCheckboxChange(checkbox) {
      var evt;
      try {
        evt = new Event('change', { bubbles: true });
      } catch (err) {
        evt = document.createEvent('Event');
        evt.initEvent('change', true, true);
      }
      checkbox.dispatchEvent(evt);
    }

    // Listen for changes on the entire grid (event delegation)
    grid.addEventListener('change', function (e) {
      if (e.target && e.target.type === 'checkbox') {
        syncBadges();
      }
    });

    // Clicking a cell (but not the checkbox/label itself) should toggle the checkbox
    for (var ci = 0; ci < cells.length; ci++) {
      (function (cell, cb) {
        cell.addEventListener('click', function (e) {
          var tag = e.target.tagName.toUpperCase();
          if (tag === 'INPUT' || tag === 'LABEL') return;
          if (cb) {
            cb.checked = !cb.checked;
            dispatchCheckboxChange(cb);
          }
        });
      })(cells[ci], checkboxes[ci]);
    }


    // -- Deselect all --
    if (deselectAllBtn) {
      deselectAllBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        for (var j = 0; j < checkboxes.length; j++) {
          if (checkboxes[j] && checkboxes[j].checked) {
            checkboxes[j].checked = false;
            dispatchCheckboxChange(checkboxes[j]);
          }
        }
        syncBadges();
      });
    }

    // -- Initial state --
    syncBadges();
  }

  // Initialise all widgets
  function initAll() {
    var widgets = document.querySelectorAll('.language-grid-widget');
    for (var i = 0; i < widgets.length; i++) {
      initLanguageGrid(widgets[i]);
    }
  }

  // Run init when DOM is ready, using multiple strategies for reliability
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

  // Also run on window load as a fallback (covers edge cases with compressed bundles)
  window.addEventListener('load', initAll);
})();

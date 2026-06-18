const MAX_VISIBLE_BADGES = 8;

function dispatchCheckboxChange(checkbox) {
  checkbox.dispatchEvent(new Event('change', { bubbles: true }));
}

function getSelectedLanguages(cells, checkboxes) {
  return cells.reduce((selected, cell, index) => {
    const checkbox = checkboxes[index];
    if (!checkbox) return selected;

    cell.classList.toggle('is-checked', checkbox.checked);
    if (checkbox.checked) {
      selected.push({
        code: checkbox.value,
        name: cell.getAttribute('data-language-name') || checkbox.value,
      });
    }
    return selected;
  }, []);
}

function renderBadge(container, className, text) {
  const badge = document.createElement('span');
  badge.className = className;
  badge.textContent = text;
  container.appendChild(badge);
}

export function initLanguageGrid(widget) {
  if (widget.dataset.languageGridInit === 'true') return;

  const summary = widget.querySelector('[data-language-grid-summary]');
  const panel = widget.querySelector('[data-language-grid-panel]');
  const searchInput = widget.querySelector('[data-language-grid-search]');
  const grid = widget.querySelector('[data-language-grid-grid]');
  const badgesContainer = widget.querySelector('[data-language-grid-badges]');
  const countLabel = widget.querySelector('[data-language-grid-count]');
  const noResults = widget.querySelector('[data-language-grid-no-results]');
  const deselectAllBtn = widget.querySelector('[data-language-grid-deselect-all]');

  if (!summary || !panel || !grid) return;

  widget.dataset.languageGridInit = 'true';
  widget.classList.add('is-ready');
  panel.hidden = true;

  const emptyText = countLabel?.dataset.emptyText || countLabel?.textContent.trim() || '';
  const requiredMarker = countLabel?.querySelector('[data-language-grid-required]')?.outerHTML || '';
  const selectedSingularText = countLabel?.dataset.selectedSingularText || '';
  const selectedPluralText = countLabel?.dataset.selectedPluralText || selectedSingularText;
  const overflowText = countLabel?.dataset.overflowText || '';
  const cells = Array.from(grid.querySelectorAll('[data-language-grid-cell]'));
  const checkboxes = cells.map((cell) => cell.querySelector('input[type="checkbox"]'));

  function setCountLabel(text) {
    if (countLabel) {
      countLabel.innerHTML = `${text}${requiredMarker}`;
    }
  }

  function syncBadges() {
    if (!badgesContainer) return;

    badgesContainer.innerHTML = '';
    const selected = getSelectedLanguages(cells, checkboxes);

    selected.slice(0, MAX_VISIBLE_BADGES).forEach((language) => {
      renderBadge(badgesContainer, 'language-grid-badge', language.name);
    });

    if (selected.length > MAX_VISIBLE_BADGES) {
      const hiddenCount = selected.length - MAX_VISIBLE_BADGES;
      renderBadge(
        badgesContainer,
        'language-grid-badge-overflow',
        `+${hiddenCount}${overflowText ? ` ${overflowText}` : ''}`,
      );
    }

    if (selected.length === 0) {
      setCountLabel(emptyText);
    } else {
      const selectedText = selected.length === 1 ? selectedSingularText : selectedPluralText;
      setCountLabel(`${selected.length}${selectedText ? ` ${selectedText}` : ''}`);
    }
  }

  summary.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();

    const isExpanded = widget.classList.toggle('is-expanded');
    summary.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
    panel.hidden = !isExpanded;

    if (isExpanded && searchInput) {
      setTimeout(() => searchInput.focus(), 50);
    }
  });

  summary.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      summary.click();
    }
  });

  searchInput?.addEventListener('input', () => {
    const query = searchInput.value.trim().toLowerCase();
    let visibleCount = 0;

    cells.forEach((cell, index) => {
      const label = (cell.getAttribute('data-language-name') || '').toLowerCase();
      const code = (checkboxes[index]?.value || '').toLowerCase();
      const matches = !query || label.includes(query) || code.includes(query);
      cell.classList.toggle('is-hidden', !matches);
      if (matches) visibleCount++;
    });

    noResults?.classList.toggle('is-visible', visibleCount === 0);
  });

  searchInput?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
    }
  });

  grid.addEventListener('change', (event) => {
    if (event.target?.type === 'checkbox') {
      syncBadges();
    }
  });

  cells.forEach((cell, index) => {
    cell.addEventListener('click', (event) => {
      const tag = event.target.tagName.toUpperCase();
      if (tag === 'INPUT' || tag === 'LABEL') return;

      const checkbox = checkboxes[index];
      if (checkbox) {
        checkbox.checked = !checkbox.checked;
        dispatchCheckboxChange(checkbox);
      }
    });
  });

  deselectAllBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();

    checkboxes.forEach((checkbox) => {
      if (checkbox?.checked) {
        checkbox.checked = false;
        dispatchCheckboxChange(checkbox);
      }
    });
    syncBadges();
  });

  syncBadges();
}

export function initAllLanguageGrids() {
  document.querySelectorAll('.language-grid-widget').forEach(initLanguageGrid);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAllLanguageGrids);
} else {
  initAllLanguageGrids();
}

window.addEventListener('load', initAllLanguageGrids);

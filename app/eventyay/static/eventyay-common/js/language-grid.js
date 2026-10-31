const MAX_VISIBLE_BADGES = 8;
const localeOrderByWidget = new WeakMap();
let orderedSubmitBound = false;

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

function checkedLanguageCodes(checkboxes) {
  return checkboxes.filter((checkbox) => checkbox?.checked).map((checkbox) => checkbox.value);
}

function rememberLocaleOrder(widget, checkboxes) {
  const checked = checkedLanguageCodes(checkboxes);
  const checkedSet = new Set(checked);
  let order = (localeOrderByWidget.get(widget) || []).filter((code) => checkedSet.has(code));

  if (order.length === 0) {
    const savedOrder = (widget.dataset.selectedOrder || '').split(',').filter(Boolean);
    savedOrder.forEach((code) => {
      if (checkedSet.has(code) && !order.includes(code)) order.push(code);
    });
    const defaultInput = document.getElementById(widget.dataset.defaultLocaleInput || '');
    if (defaultInput && checkedSet.has(defaultInput.value)) {
      order = order.filter((code) => code !== defaultInput.value);
      order.unshift(defaultInput.value);
    }
  }

  checked.forEach((code) => {
    if (!order.includes(code)) order.push(code);
  });
  localeOrderByWidget.set(widget, order);
  return order;
}

function moveLocale(widget, checkboxes, code, toIndex) {
  const order = rememberLocaleOrder(widget, checkboxes);
  const fromIndex = order.indexOf(code);
  if (fromIndex === -1 || toIndex < 0 || toIndex >= order.length || fromIndex === toIndex) return order;
  order.splice(fromIndex, 1);
  order.splice(toIndex, 0, code);
  localeOrderByWidget.set(widget, order);
  return order;
}

function languageName(widget, code) {
  const cell = widget.querySelector(`[data-language-grid-cell] input[type="checkbox"][value="${CSS.escape(code)}"]`)
    ?.closest('[data-language-grid-cell]');
  return cell?.getAttribute('data-language-name') || code;
}

function syncDefaultLocaleInput(widget, order) {
  const defaultInput = document.getElementById(widget.dataset.defaultLocaleInput || '');
  if (defaultInput && order[0]) defaultInput.value = order[0];
}

function renderOrderedDefaultBadges(widget, checkboxes, badgesContainer, countLabel, emptyText, focusedCode = null) {
  const order = rememberLocaleOrder(widget, checkboxes);
  badgesContainer.replaceChildren();
  syncDefaultLocaleInput(widget, order);

  order.forEach((code, index) => {
    const badge = document.createElement('span');
    const labelText = languageName(widget, code);
    const isDefault = index === 0;
    badge.className = `language-grid-badge${isDefault ? ' is-default-language' : ''}`;
    badge.draggable = true;
    badge.tabIndex = 0;
    badge.setAttribute('role', 'button');
    badge.dataset.code = code;
    badge.setAttribute(
      'aria-label',
      isDefault
        ? `${labelText} (${widget.dataset.labelDefault || 'Default language'})`
        : `${labelText}. ${widget.dataset.labelSetDefault || ''}`,
    );
    badge.title = isDefault
      ? (widget.dataset.labelDefault || 'Default language')
      : (widget.dataset.labelReorder || '');

    const handle = document.createElement('span');
    handle.className = 'drag-handle';
    handle.textContent = '⠿';
    handle.setAttribute('aria-hidden', 'true');
    badge.appendChild(handle);

    const text = document.createElement('span');
    text.textContent = labelText;
    badge.appendChild(text);

    const applyOrder = (nextOrder, isKeyboard = false) => {
      localeOrderByWidget.set(widget, nextOrder);
      renderOrderedDefaultBadges(
        widget,
        checkboxes,
        badgesContainer,
        countLabel,
        emptyText,
        isKeyboard ? code : null,
      );
    };

    badge.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (!isDefault) applyOrder(moveLocale(widget, checkboxes, code, 0));
    });
    badge.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        event.stopPropagation();
        if (!isDefault) applyOrder(moveLocale(widget, checkboxes, code, 0), true);
      } else if (event.key === 'ArrowLeft' && index > 0) {
        event.preventDefault();
        event.stopPropagation();
        applyOrder(moveLocale(widget, checkboxes, code, index - 1), true);
      } else if (event.key === 'ArrowRight' && index < order.length - 1) {
        event.preventDefault();
        event.stopPropagation();
        applyOrder(moveLocale(widget, checkboxes, code, index + 1), true);
      }
    });
    badge.addEventListener('dragstart', (event) => {
      badge.classList.add('dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', code);
    });
    badge.addEventListener('dragend', () => {
      badge.classList.remove('dragging');
    });
    badge.addEventListener('dragover', (event) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
    });
    badge.addEventListener('drop', (event) => {
      event.preventDefault();
      event.stopPropagation();
      const draggedCode = event.dataTransfer.getData('text/plain');
      if (!draggedCode || draggedCode === code) return;
      const current = rememberLocaleOrder(widget, checkboxes);
      const toIndex = current.indexOf(code);
      if (toIndex === -1) return;
      applyOrder(moveLocale(widget, checkboxes, draggedCode, toIndex));
    });

    badgesContainer.appendChild(badge);
  });

  if (countLabel) {
    countLabel.textContent = order.length === 0 ? emptyText : '';
    countLabel.style.display = order.length === 0 ? '' : 'none';
  }

  if (focusedCode) {
    const refocus = Array.from(badgesContainer.children).find((el) => el.dataset.code === focusedCode);
    if (refocus) refocus.focus();
  }
}

function writeOrderedLocaleInputs(widget) {
  const checkboxes = Array.from(widget.querySelectorAll('[data-language-grid-cell] input[type="checkbox"]'));
  const order = rememberLocaleOrder(widget, checkboxes);
  const fieldName = checkboxes.find((checkbox) => checkbox.name)?.name
    || checkboxes.find((checkbox) => checkbox.dataset.orderedLocaleName)?.dataset.orderedLocaleName;
  if (!fieldName || order.length === 0) return;

  checkboxes.forEach((checkbox) => {
    checkbox.dataset.orderedLocaleName = checkbox.name;
    checkbox.removeAttribute('name');
  });
  widget.querySelector('[data-ordered-locale-inputs]')?.remove();
  const container = document.createElement('div');
  container.hidden = true;
  container.dataset.orderedLocaleInputs = 'true';
  order.forEach((code) => {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = fieldName;
    input.value = code;
    container.appendChild(input);
  });
  widget.appendChild(container);
  syncDefaultLocaleInput(widget, order);
}

function bindOrderedLocaleSubmit() {
  if (orderedSubmitBound) return;
  orderedSubmitBound = true;
  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    form.querySelectorAll('.language-grid-widget[data-ordered-default="true"]').forEach(writeOrderedLocaleInputs);
  }, true);
}

export function initLanguageGrid(widget) {
  if (widget.dataset.languageGridInit === 'true') return;

  const summary = widget.querySelector('[data-language-grid-summary]');
  const panel = widget.querySelector('[data-language-grid-panel]');
  const searchInput = widget.querySelector('[data-language-grid-search]');
  const grid = widget.querySelector('[data-language-grid-grid]');
  const badgesContainer = widget.querySelector('[data-language-grid-badges]');
  const noResults = widget.querySelector('[data-language-grid-no-results]');
  const deselectAllBtn = widget.querySelector('[data-language-grid-deselect-all]');

  if (!summary || !panel || !grid) return;

  widget.dataset.languageGridInit = 'true';
  widget.classList.add('is-ready');
  panel.hidden = true;
  if (widget.dataset.orderedDefault === 'true') bindOrderedLocaleSubmit();

  const countLabel = widget.querySelector('[data-language-grid-count]');
  const emptyText = countLabel?.dataset.emptyText || countLabel?.textContent.trim() || '';
  const cells = Array.from(grid.querySelectorAll('[data-language-grid-cell]'));
  const checkboxes = cells.map((cell) => cell.querySelector('input[type="checkbox"]'));

  function syncBadges() {
    if (!badgesContainer) return;
    if (widget.dataset.orderedDefault === 'true') {
      renderOrderedDefaultBadges(widget, checkboxes, badgesContainer, countLabel, emptyText);
      return;
    }
    if (badgesContainer.dataset.customBadges === 'true' || widget.dataset.customBadges === 'true') return;

    badgesContainer.innerHTML = '';
    const selected = getSelectedLanguages(cells, checkboxes);

    selected.forEach((language) => {
      renderBadge(badgesContainer, 'language-grid-badge', language.name);
    });

    if (countLabel) {
      if (selected.length === 0) {
        countLabel.textContent = emptyText;
        countLabel.style.display = '';
      } else {
        countLabel.textContent = '';
        countLabel.style.display = 'none';
      }
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

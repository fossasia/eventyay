(() => {
  const escapeCss = (value) => {
    if (window.CSS && window.CSS.escape) {
      return window.CSS.escape(value);
    }
    return value.replace(/([.#:[\\],])/g, '\\\\$1');
  };

  const initWidget = (container) => {
    if (!container || container.dataset.mlInitialized) {
      return;
    }
    container.dataset.mlInitialized = 'true';

    const picker = container.querySelector('[data-role="picker"]');
    const hiddenSelect = container.querySelector('[data-role="hidden-select"]');
    const selectedList = container.querySelector('[data-role="selected-list"]');
    const defaultLocaleSelect = document.querySelector('select[name$="locale"]');
    const emptyText = (container.querySelector('[data-role="i18n-empty"]') || {}).textContent || '';
    const removeLabel = (container.querySelector('[data-role="i18n-remove"]') || {}).textContent || '';

    if (!picker || !hiddenSelect || !selectedList) {
      return;
    }

    const getSelectedValues = () =>
      Array.from(hiddenSelect.querySelectorAll('option')).filter((opt) => opt.selected).map((opt) => opt.value);

    const removeEmptyPlaceholder = () => {
      const empty = selectedList.querySelector('[data-role="empty"]');
      if (empty) {
        empty.remove();
      }
    };

    const ensureEmptyPlaceholder = () => {
      if (!selectedList.querySelector('[data-role="selected-badge"]')) {
        const placeholder = document.createElement('span');
        placeholder.className = 'text-muted';
        placeholder.dataset.role = 'empty';
        placeholder.textContent = emptyText;
        selectedList.appendChild(placeholder);
      }
    };

    const hiddenOptionText = (value) => {
      const hiddenOption = hiddenSelect.querySelector('option[value="' + escapeCss(value) + '"]');
      return hiddenOption ? hiddenOption.textContent : value;
    };

    const togglePickerOption = (value, available) => {
      const option = picker.querySelector('option[value="' + escapeCss(value) + '"]');
      if (option) {
        option.hidden = !available;
        option.disabled = !available;
        if (!available && picker.value === value) {
          picker.value = '';
        }
        if (available && !option.label) {
          option.textContent = hiddenOptionText(value);
        }
      } else if (available) {
        const hiddenOption = hiddenSelect.querySelector('option[value="' + escapeCss(value) + '"]');
        if (hiddenOption) {
          picker.appendChild(new Option(hiddenOption.textContent, hiddenOption.value));
        }
      }
    };

    const addBadge = (value) => {
      removeEmptyPlaceholder();
      if (selectedList.querySelector('[data-lang="' + escapeCss(value) + '"]')) {
        return;
      }
      const hiddenOption = hiddenSelect.querySelector('option[value="' + escapeCss(value) + '"]');
      const label = hiddenOption ? hiddenOption.textContent : value;

      const badge = document.createElement('span');
      badge.className = 'language-badge';
      badge.setAttribute('role', 'button');
      badge.setAttribute('tabindex', '0');
      badge.dataset.lang = value;
      badge.dataset.role = 'selected-badge';

      const textSpan = document.createElement('span');
      textSpan.className = 'language-label';
      textSpan.textContent = label;
      badge.appendChild(textSpan);

      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'remove-language-btn btn btn-link btn-sm p-0 ml-1 align-baseline text-white';
      removeBtn.setAttribute('aria-label', removeLabel);
      removeBtn.innerHTML = '&times;';
      removeBtn.dataset.role = 'remove-language';
      removeBtn.dataset.value = value;
      removeBtn.addEventListener('click', (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        removeLanguage(value);
      });
      badge.appendChild(removeBtn);

      badge.addEventListener('click', (ev) => {
        if (ev.target.closest('[data-role="remove-language"]')) return;
        removeLanguage(value);
      });
      badge.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          removeLanguage(value);
        }
      });

      selectedList.appendChild(badge);
    };

    const addLanguage = (value) => {
      if (!value) {
        return;
      }
      const hiddenOption = hiddenSelect.querySelector('option[value="' + escapeCss(value) + '"]');
      if (hiddenOption) {
        hiddenOption.selected = true;
        addBadge(value);
        togglePickerOption(value, false);
      }
      picker.value = '';
    };

    const removeLanguage = (value) => {
      const hiddenOption = hiddenSelect.querySelector('option[value="' + escapeCss(value) + '"]');
      if (!hiddenOption || !hiddenOption.selected) {
        return;
      }

      hiddenOption.selected = false;
      const badge = selectedList.querySelector('[data-lang="' + escapeCss(value) + '"]');
      if (badge) {
        badge.remove();
      }
      if (defaultLocaleSelect && defaultLocaleSelect.value === value) {
        const remaining = getSelectedValues();
        defaultLocaleSelect.value = remaining.length ? remaining[0] : '';
      }
      togglePickerOption(value, true);
      ensureEmptyPlaceholder();
    };

    picker.addEventListener('change', () => addLanguage(picker.value));
    selectedList.addEventListener('click', (ev) => {
      const btn = ev.target.closest('[data-role="remove-language"]');
      if (btn) {
        ev.preventDefault();
        ev.stopPropagation();
        removeLanguage(btn.dataset.value);
      }
    });

    hiddenSelect.querySelectorAll('option').forEach((option) => {
      if (option.selected) {
        addBadge(option.value);
        togglePickerOption(option.value, false);
      }
    });
    ensureEmptyPlaceholder();

    if (defaultLocaleSelect) {
      const selectedValueSet = new Set(getSelectedValues());
      if (!selectedValueSet.has(defaultLocaleSelect.value)) {
        const firstSelected = Array.from(selectedValueSet)[0];
        if (firstSelected) {
          defaultLocaleSelect.value = firstSelected;
        }
      }
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.multi-language-select-wrapper').forEach((container) => initWidget(container));
  });
})();

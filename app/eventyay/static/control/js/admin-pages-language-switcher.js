/* Compact per-language editing for the admin Pages tabs.
 *
 * Each Pages tab renders every enabled page language as a stacked i18n widget.
 * This switcher shows a single language at a time and toggles the visibility of
 * the matching per-locale widgets in the surrounding form, so the form no longer
 * grows vertically with every language.  "Add language" enables an extra page
 * language by submitting the form with the additional locale.
 */
(() => {
    const normalize = (value) => String(value || '').toLowerCase();

    function collectUnits(form) {
        const units = [];
        form.querySelectorAll('.i18n-form-group').forEach((group) => {
            const wrappers = group.querySelectorAll('.i18n-textarea-wrapper[data-lang]');
            if (wrappers.length) {
                wrappers.forEach((wrapper) => {
                    units.push({ locale: normalize(wrapper.getAttribute('data-lang')), el: wrapper });
                });
            } else {
                group.querySelectorAll('[lang]').forEach((field) => {
                    units.push({ locale: normalize(field.getAttribute('lang')), el: field, field });
                });
            }
        });
        return units;
    }

    function unitHasContent(unit) {
        const field = unit.field || unit.el.querySelector('textarea, input');
        return field ? String(field.value || '').trim().length > 0 : false;
    }

    function initSwitcher(switcher) {
        const form = switcher.closest('form');
        if (!form) return;

        const pills = Array.from(switcher.querySelectorAll('.page-language-pill'));
        if (!pills.length) return;

        const units = collectUnits(form);

        const apply = (locale) => {
            units.forEach((unit) => {
                const visible = unit.locale === locale;
                unit.el.style.display = visible ? '' : 'none';
                if (visible) {
                    unit.el.removeAttribute('hidden');
                } else {
                    unit.el.setAttribute('hidden', '');
                }
            });
            pills.forEach((pill) => {
                pill.classList.toggle('active', normalize(pill.getAttribute('data-locale')) === locale);
            });
            refreshRemoveButtons();
        };

        const refreshIndicators = () => {
            const hasContent = {};
            units.forEach((unit) => {
                if (!(unit.locale in hasContent)) hasContent[unit.locale] = false;
                if (unitHasContent(unit)) hasContent[unit.locale] = true;
            });
            pills.forEach((pill) => {
                const locale = normalize(pill.getAttribute('data-locale'));
                pill.classList.toggle('has-content', Boolean(hasContent[locale]));
            });
        };

        const refreshRemoveButtons = () => {
            // Hide the remove button when only one language remains.
            const visiblePills = pills.filter((p) => !p.hidden);
            pills.forEach((pill) => {
                const btn = pill.querySelector('.page-language-pill-remove');
                if (btn) btn.style.display = visiblePills.length <= 1 ? 'none' : '';
            });
        };

        pills.forEach((pill) => {
            pill.addEventListener('click', (e) => {
                if (e.target.closest('.page-language-pill-remove')) return;
                apply(normalize(pill.getAttribute('data-locale')));
            });

            const removeBtn = document.createElement('span');
            removeBtn.className = 'page-language-pill-remove';
            removeBtn.setAttribute('role', 'button');
            removeBtn.setAttribute('aria-label', 'Remove language');
            removeBtn.title = 'Remove language';
            removeBtn.innerHTML = '&times;';
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const locale = normalize(pill.getAttribute('data-locale'));
                const label = pill.querySelector('.page-language-pill-name');
                const name = label ? label.textContent.trim() : locale;
                if (!window.confirm('Remove "' + name + '" from all page content? This cannot be undone.')) return;

                // POST to the dedicated remove endpoint which clears every
                // content key for this locale across all tabs, then updates page_locales.
                const removeUrl = switcher.getAttribute('data-remove-url');
                if (!removeUrl) return;
                const form2 = document.createElement('form');
                form2.method = 'post';
                form2.action = removeUrl;
                const csrf = document.querySelector('[name=csrfmiddlewaretoken]');
                if (csrf) form2.appendChild(csrf.cloneNode());
                const inp = document.createElement('input');
                inp.type = 'hidden'; inp.name = 'locale'; inp.value = locale;
                form2.appendChild(inp);
                const next = document.createElement('input');
                next.type = 'hidden'; next.name = 'next'; next.value = window.location.href;
                form2.appendChild(next);
                document.body.appendChild(form2);
                form2.submit();
            });
            pill.appendChild(removeBtn);
        });

        const addSelect = switcher.querySelector('.page-language-add');
        if (addSelect) {
            addSelect.addEventListener('change', () => {
                const locale = normalize(addSelect.value);
                if (!locale) return;
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'page_locales';
                input.value = locale;
                switcher.appendChild(input);
                form.submit();
            });
        }

        refreshIndicators();
        refreshRemoveButtons();
        form.addEventListener('input', refreshIndicators);
        apply(normalize(pills[0].getAttribute('data-locale')));
    }

    function init() {
        document.querySelectorAll('[data-page-language-switcher]').forEach(initSwitcher);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

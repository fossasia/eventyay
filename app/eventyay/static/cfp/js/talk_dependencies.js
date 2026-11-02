/**
 * Talk-specific runtime dependency evaluator for custom fields
 * Handles dependent question visibility in talk forms.
 * Supports both plain `question_<id>` names and form-prefixed variants
 * such as `speaker-question_<id>` used in the organiser create-proposal form.
 */

function talkDependenciesToggle(ev) {
    function findParentElement(el, parentName) {
        const formScope = (el && el.closest) ? (el.closest('form') || document) : document;

        // Derive prefix from the dependent element (e.g. "speaker-")
        let prefix = '';
        if (el) {
            const elName = (el.getAttribute && el.getAttribute('name')) ||
                (el.querySelector && el.querySelector('[name]') ? el.querySelector('[name]').getAttribute('name') : '') || '';
            const match = elName.match(/^(.*-)question_/);
            if (match) {
                prefix = match[1];
            }
        }

        const prefixes = prefix ? [prefix, ''] : ['', 'speaker-'];
        for (const p of prefixes) {
            const fullName = p + parentName;
            const sel = formScope.querySelector('select[name="' + fullName + '"]');
            if (sel) return { element: sel, type: 'select' };
            const radios = formScope.querySelectorAll('input[type="radio"][name="' + fullName + '"]');
            if (radios.length) return { element: radios, type: 'radio' };
            const checkboxes = Array.from(formScope.querySelectorAll('input[type="checkbox"][name="' + fullName + '"]'));
            const boolCb = checkboxes.find(function(cb) { return !cb.value || cb.value === 'on'; });
            if (boolCb) return { element: boolCb, type: 'checkbox' };
            const multiCbs = checkboxes.filter(function(cb) { return cb.value && cb.value !== 'on'; });
            if (multiCbs.length) return { element: multiCbs, type: 'multi_checkbox' };
        }
        return null;
    }

    function shouldBeShown(el) {
        if (!el.dataset.questionDependency) {
            return true;
        }

        const dependencyId = el.dataset.questionDependency;
        let dependencyValues;
        try {
            dependencyValues = JSON.parse(el.dataset.questionDependencyValues);
        } catch (e) {
            return true;
        }
        const parentName = 'question_' + dependencyId;

        const found = findParentElement(el, parentName);
        if (!found) return false;

        if (found.type === 'select') {
            const select = found.element;
            const selectContainer = select.closest(".form-group");
            if (selectContainer && !selectContainer.classList.contains("dependency-hidden")) {
                if (select.multiple) {
                    const selectedValues = Array.from(select.selectedOptions).map(function(opt) {
                        return opt.value;
                    });
                    return shouldBeShown(select) && selectedValues.some(function(val) {
                        return dependencyValues.indexOf(val) > -1;
                    });
                }
                return shouldBeShown(select) && dependencyValues.indexOf(select.value) > -1;
            }
        }

        if (found.type === 'radio') {
            const radioGroup = found.element;
            const checkedRadio = Array.from(radioGroup).find(function(r) { return r.checked; });
            const radioContainer = radioGroup[0].closest(".form-group");
            if (radioContainer && !radioContainer.classList.contains("dependency-hidden")) {
                return shouldBeShown(radioGroup[0]) && checkedRadio && dependencyValues.indexOf(checkedRadio.value) > -1;
            }
        }

        if (found.type === 'checkbox') {
            const checkbox = found.element;
            if (dependencyValues.indexOf("True") > -1 || dependencyValues.indexOf("False") > -1) {
                const checkboxContainer = checkbox.closest(".form-group");
                if (checkboxContainer && !checkboxContainer.classList.contains("dependency-hidden")) {
                    return shouldBeShown(checkbox) && (
                        (dependencyValues.indexOf("True") > -1 && checkbox.checked)
                        || (dependencyValues.indexOf("False") > -1 && !checkbox.checked)
                    );
                }
            }
        }

        if (found.type === 'multi_checkbox') {
            const multiCheckboxes = found.element;
            const checkedBoxes = multiCheckboxes.filter(function(cb) { return cb.checked; });
            const multiContainer = multiCheckboxes[0].closest(".form-group");
            if (multiContainer && !multiContainer.classList.contains("dependency-hidden")) {
                for (let i = 0; i < dependencyValues.length; i++) {
                    const val = dependencyValues[i].toString();
                    if (checkedBoxes.some(function(cb) { return cb.value === val; })) {
                        return shouldBeShown(multiCheckboxes[0]);
                    }
                }
            }
        }

        return false;
    }

    document.querySelectorAll("[data-question-dependency]").forEach(function(el) {
        const dependent = el.closest(".form-group");
        if (!dependent) return;
        
        const isShown = !dependent.classList.contains("dependency-hidden");
        const shouldShow = shouldBeShown(el);

        if (shouldShow) {
            if (!isShown) {
                dependent.classList.remove("dependency-hidden");
            }
            dependent.querySelectorAll("input.required-hidden, select.required-hidden, textarea.required-hidden").forEach(function(field) {
                field.required = true;
                field.classList.remove("required-hidden");
            });
        } else if (isShown) {
            if (dependent.classList.contains("has-error") || dependent.querySelector(".has-error")) {
                return;
            }
            dependent.classList.add("dependency-hidden");
            dependent.querySelectorAll("input[required], select[required], textarea[required]").forEach(function(field) {
                field.required = false;
                field.classList.add("required-hidden");
            });
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    talkDependenciesToggle();
    
    document.addEventListener('change', function(e) {
        const target = e.target;
        if ((target.tagName === 'INPUT' || target.tagName === 'SELECT') && 
            target.name && (target.name.startsWith('question_') || target.name.includes('-question_'))) {
            talkDependenciesToggle(e);
        }
    });
});

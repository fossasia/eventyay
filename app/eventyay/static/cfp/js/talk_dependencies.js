/**
 * Talk-specific runtime dependency evaluator for custom fields
 * Rewritten in vanilla JavaScript
 */

(function() {
    'use strict';

function talkDependenciesToggle(ev) {
    function shouldBeShown(el) {
        if (!el.dataset.questionDependency) {
            return true;
        }

        var dependencyId = el.dataset.questionDependency;
        var dependencyValues = JSON.parse(el.dataset.questionDependencyValues);
        var parentName = 'question_' + dependencyId;

        // Check for select (single choice dropdown)
        var select = document.querySelector('select[name="' + parentName + '"]');
        if (select) {
            var selectContainer = select.closest(".form-group");
            if (selectContainer && !selectContainer.classList.contains("dependency-hidden")) {
                return shouldBeShown(select) && dependencyValues.indexOf(select.value) > -1;
            }
        }

        // Check for radio buttons (single choice radio)
        var radioGroup = document.querySelectorAll('input[type="radio"][name="' + parentName + '"]');
        if (radioGroup.length) {
            var checkedRadio = Array.from(radioGroup).find(function(r) { return r.checked; });
            var radioContainer = radioGroup[0].closest(".form-group");
            if (radioContainer && !radioContainer.classList.contains("dependency-hidden")) {
                return shouldBeShown(radioGroup[0]) && checkedRadio && dependencyValues.indexOf(checkedRadio.value) > -1;
            }
        }

        // Check for boolean checkbox (single checkbox without value attribute)
        var checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"][name="' + parentName + '"]'));
        var checkbox = checkboxes.find(function(cb) { return !cb.value || cb.value === 'on'; });
        if (checkbox && (dependencyValues.indexOf("True") > -1 || dependencyValues.indexOf("False") > -1)) {
            var checkboxContainer = checkbox.closest(".form-group");
            if (checkboxContainer && !checkboxContainer.classList.contains("dependency-hidden")) {
                return shouldBeShown(checkbox) && (
                    (dependencyValues.indexOf("True") > -1 && checkbox.checked)
                    || (dependencyValues.indexOf("False") > -1 && !checkbox.checked)
                );
            }
        }

        // Check for multiple checkboxes (multiple choice with value attribute)
        var multiCheckboxes = Array.from(document.querySelectorAll('input[type="checkbox"][name="' + parentName + '"]')).filter(function(cb) {
            return cb.value && cb.value !== 'on';
        });
        if (multiCheckboxes.length) {
            var checkedBoxes = multiCheckboxes.filter(function(cb) { return cb.checked; });
            var multiContainer = multiCheckboxes[0].closest(".form-group");
            if (multiContainer && !multiContainer.classList.contains("dependency-hidden")) {
                for (var i = 0; i < dependencyValues.length; i++) {
                    var val = dependencyValues[i].toString();
                    if (checkedBoxes.some(function(cb) { return cb.value === val; })) {
                        return shouldBeShown(multiCheckboxes[0]);
                    }
                }
            }
        }

        return false;
    }

    document.querySelectorAll("[data-question-dependency]").forEach(function(el) {
        var dependent = el.closest(".form-group");
        if (!dependent) return;
        
        var isShown = !dependent.classList.contains("dependency-hidden");
        var shouldShow = shouldBeShown(el);

        if (shouldShow && !isShown) {
            dependent.classList.remove("dependency-hidden");
            dependent.querySelectorAll("input.required-hidden, select.required-hidden, textarea.required-hidden").forEach(function(field) {
                field.required = true;
                field.classList.remove("required-hidden");
            });
        } else if (!shouldShow && isShown) {
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
        var target = e.target;
        if ((target.tagName === 'INPUT' || target.tagName === 'SELECT') && 
            target.name && target.name.startsWith('question_')) {
            talkDependenciesToggle(e);
        }
    });
});

})();

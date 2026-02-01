/**
 * Talk-specific runtime dependency evaluator for custom fields
 * Mirrors the behavior of pretixpresale/js/ui/questions.js
 */

function talkDependenciesToggle(ev) {
    function shouldBeShown($el) {
        if (!$el.attr('data-question-dependency')) {
            return true;
        }

        var dependencyId = $el.attr('data-question-dependency');
        var dependencyValues = JSON.parse($el.attr('data-question-dependency-values'));
        var parentName = 'question_' + dependencyId;

        // Check for select (single choice dropdown)
        var $select = $("select[name=" + parentName + "]");
        if ($select.length) {
            if (!$select.closest(".form-group").hasClass("dependency-hidden")) {
                return shouldBeShown($select) && $.inArray($select.val(), dependencyValues) > -1;
            }
        }

        // Check for radio buttons (single choice radio)
        var $radioGroup = $("input[type=radio][name=" + parentName + "]");
        if ($radioGroup.length) {
            var $checkedRadio = $radioGroup.filter(":checked");
            var $radioContainer = $radioGroup.closest(".form-group").first();
            if (!$radioContainer.hasClass("dependency-hidden")) {
                return shouldBeShown($radioGroup.first()) && $checkedRadio.length && $.inArray($checkedRadio.val(), dependencyValues) > -1;
            }
        }

        // Check for boolean checkbox (single checkbox without value attribute)
        var $checkbox = $("input[type=checkbox][name=" + parentName + "]").filter(function() {
            return !this.value || this.value === 'on';
        });
        if ($checkbox.length && ($.inArray("True", dependencyValues) > -1 || $.inArray("False", dependencyValues) > -1)) {
            if (!$checkbox.closest(".form-group").hasClass("dependency-hidden")) {
                return shouldBeShown($checkbox) && (
                    ($.inArray("True", dependencyValues) > -1 && $checkbox.prop('checked'))
                    || ($.inArray("False", dependencyValues) > -1 && !$checkbox.prop('checked'))
                );
            }
        }

        // Check for multiple checkboxes (multiple choice with value attribute)
        var $multiCheckboxes = $("input[type=checkbox][name=" + parentName + "]").filter(function() {
            return this.value && this.value !== 'on';
        });
        if ($multiCheckboxes.length) {
            var $checkedBoxes = $multiCheckboxes.filter(":checked");
            var $multiContainer = $multiCheckboxes.closest(".form-group").first();
            if (!$multiContainer.hasClass("dependency-hidden")) {
                for (var i = 0; i < dependencyValues.length; i++) {
                    if ($checkedBoxes.filter("[value=" + dependencyValues[i] + "]").length) {
                        return shouldBeShown($multiCheckboxes.first());
                    }
                }
            }
        }

        return false;
    }

    $("[data-question-dependency]").each(function () {
        var $dependent = $(this).closest(".form-group");
        var isShown = !$dependent.hasClass("dependency-hidden");
        var shouldShow = shouldBeShown($(this));

        if (shouldShow && !isShown) {
            $dependent.stop().removeClass("dependency-hidden");
            if (!ev) {
                $dependent.show();
            } else {
                $dependent.slideDown();
            }
            $dependent.find("input.required-hidden, select.required-hidden, textarea.required-hidden").each(function () {
                $(this).prop("required", true).removeClass("required-hidden");
            });
        } else if (!shouldShow && isShown) {
            if ($dependent.hasClass("has-error") || $dependent.find(".has-error").length) {
                return;
            }
            $dependent.stop().addClass("dependency-hidden");
            if (!ev) {
                $dependent.hide();
            } else {
                $dependent.slideUp();
            }
            $dependent.find("input[required], select[required], textarea[required]").each(function () {
                $(this).prop("required", false).addClass("required-hidden");
            });
        }
    });
}

$(function () {
    talkDependenciesToggle();
    $(document).on("change", "input[name^='question_'], select[name^='question_']", talkDependenciesToggle);
});

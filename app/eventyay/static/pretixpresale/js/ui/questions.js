/*global $,safeSelector */
function _css_escape_value(v) {
    var s = String(v);
    if (typeof window !== 'undefined' && window.CSS && typeof window.CSS.escape === 'function') {
        return window.CSS.escape(s);
    }
    return s.replace(/(["\\])/g, '\\$1');
}

function _attr_sel(name, value) {
    return '[' + name + '="' + _css_escape_value(value) + '"]';
}

function questions_toggle_dependent(ev) {
    function q_should_be_shown($el) {
        if (!$el.attr('data-question-dependency')) {
            return true;
        }

        var name = $el.attr('name') || '';
        var dep_id = $el.attr('data-question-dependency');
        var dependency_name = name.replace(/question_\d+(?:_\d+)?$/, 'question_' + dep_id);
        if (dependency_name === name) {
            dependency_name = name.split('_')[0] + '_' + dep_id;
        }

        var dependency_values;
        try {
            dependency_values = JSON.parse($el.attr('data-question-dependency-values'));
        } catch (e) {
            return true;
        }
        if (!Array.isArray(dependency_values)) {
            return true;
        }

        var nameSel = _attr_sel('name', dependency_name);
        var $dependency_el;

        $dependency_el = $('select' + nameSel);
        if ($dependency_el.length) {
            if ($dependency_el.closest('.form-group').hasClass('dependency-hidden')) {
                return false;
            }
            return q_should_be_shown($dependency_el) &&
                $.inArray($dependency_el.val(), dependency_values) > -1;
        }

        $dependency_el = $('input[type="radio"]' + nameSel);
        if ($dependency_el.length) {
            if ($dependency_el.closest('.form-group').hasClass('dependency-hidden')) {
                return false;
            }
            return q_should_be_shown($dependency_el.first()) &&
                $.inArray($dependency_el.filter(':checked').val(), dependency_values) > -1;
        }

        $dependency_el = $('input[type="checkbox"]' + nameSel);
        if ($dependency_el.length) {
            if ($dependency_el.closest('.form-group').hasClass('dependency-hidden')) {
                return false;
            }

            var has_true = $.inArray('True', dependency_values) > -1;
            var has_false = $.inArray('False', dependency_values) > -1;

            if ($dependency_el.length === 1 && (has_true || has_false)) {
                if (!q_should_be_shown($dependency_el)) {
                    return false;
                }
                var checked = $dependency_el.prop('checked');
                return (has_true && checked) || (has_false && !checked);
            }

            if (!q_should_be_shown($dependency_el.first())) {
                return false;
            }
            for (var i = 0; i < dependency_values.length; i++) {
                var sel = 'input[type="checkbox"]' +
                    _attr_sel('value', dependency_values[i]) +
                    nameSel + ':checked';
                if (safeSelector(sel).length) {
                    return true;
                }
            }
            return false;
        }

        return false;
    }

    $('[data-question-dependency]').each(function () {
        var $dependent = $(this).closest('.form-group');
        var is_shown = !$dependent.hasClass('dependency-hidden');
        var should_be_shown = q_should_be_shown($(this));

        if (should_be_shown && !is_shown) {
            $dependent.stop().removeClass('dependency-hidden');
            if (!ev) {
                $dependent.show();
            } else {
                $dependent.slideDown();
            }
            $dependent.find('input.required-hidden, select.required-hidden, textarea.required-hidden').each(function () {
                $(this).prop('required', true).removeClass('required-hidden');
            });
        } else if (!should_be_shown && is_shown) {
            if ($dependent.hasClass('has-error') || $dependent.find('.has-error').length) {
                // Do not hide things with invalid validation
                return;
            }
            $dependent.stop().addClass('dependency-hidden');
            if (!ev) {
                $dependent.hide();
            } else {
                $dependent.slideUp();
            }
            $dependent.find('input[required], select[required], textarea[required]').each(function () {
                $(this).prop('required', false).addClass('required-hidden');
            });
        }
    });
}

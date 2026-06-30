/*globals $, Morris, gettext, RRule, RRuleSet*/

$(function () {
    var reloaded = false;
    var update = function () {
        $.getJSON(location.href + '?ajax=true', {}, function (data) {
            if (data.initialized) {
                if (!reloaded) {
                    reloaded = true;
                    location.reload();
                }
            } else {
                window.setTimeout(update, 500);
            }
        });
    };
    window.setTimeout(update, 500);
});

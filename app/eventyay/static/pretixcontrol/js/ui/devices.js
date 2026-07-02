/*globals $, Morris, gettext, RRule, RRuleSet*/

$(function () {
    var reloaded = false;
    var pollUrl = new URL(window.location.href);
    pollUrl.searchParams.set('ajax', 'true');

    var update = function () {
        $.ajax({
            url: pollUrl.pathname + pollUrl.search,
            dataType: 'json',
            global: false,
            success: function (data) {
                if (data.initialized) {
                    if (!reloaded) {
                        reloaded = true;
                        location.reload();
                    }
                } else {
                    window.setTimeout(update, 500);
                }
            },
            error: function () {
                window.setTimeout(update, 500);
            }
        });
    };
    window.setTimeout(update, 500);
});

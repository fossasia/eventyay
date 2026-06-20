/*globals Morris, gettext, RRule, RRuleSet*/

(function() {
    var BASE_DELAY_MS = 1000;
    var MAX_DELAY_MS = 5000;
    var delayMs = BASE_DELAY_MS;

    var scheduleNextUpdate = function() {
        window.setTimeout(update, delayMs);
    };

    var update = function() {
        var url = new URL(location.href);
        url.searchParams.set('ajax', 'true');

        fetch(url, {
            credentials: 'same-origin',
            cache: 'no-store',
            headers: {
                Accept: 'application/json',
            },
        })
            .then(function(response) {
                if (!response.ok) {
                    throw new Error('Polling request failed with status ' + response.status);
                }
                return response.json();
            })
            .then(function(data) {
                if (data.initialized) {
                    location.reload();
                    return;
                }
                delayMs = BASE_DELAY_MS;
                scheduleNextUpdate();
            })
            .catch(function(err) {
                console.error('device initialization polling failed:', err);
                delayMs = Math.min(Math.floor(delayMs * 1.5), MAX_DELAY_MS);
                scheduleNextUpdate();
            });
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', scheduleNextUpdate);
    } else {
        scheduleNextUpdate();
    }
})();

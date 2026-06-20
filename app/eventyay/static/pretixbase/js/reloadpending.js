(function() {
    var BASE_DELAY_MS = 1000;
    var MAX_DELAY_MS = 5000;
    var delayMs = BASE_DELAY_MS;

    var scheduleNextPoll = function() {
        window.setTimeout(poll, delayMs);
    };

    var poll = function() {
        var url = new URL(location.href);
        url.searchParams.set('ajax', '1');

        fetch(url, {
            credentials: 'same-origin',
            cache: 'no-store',
        })
            .then(function(response) {
                if (!response.ok) {
                    throw new Error('Polling request failed with status ' + response.status);
                }
                return response.text();
            })
            .then(function(data) {
                if (data === '1') {
                    location.reload();
                    return;
                }
                delayMs = BASE_DELAY_MS;
                scheduleNextPoll();
            })
            .catch(function(err) {
                console.error('[reloadpending] poll request failed:', err);
                delayMs = Math.min(Math.floor(delayMs * 1.5), MAX_DELAY_MS);
                scheduleNextPoll();
            });
    };

    scheduleNextPoll();
})();

const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 5000;
let delayMs = BASE_DELAY_MS;

function scheduleNextPoll() {
    window.setTimeout(poll, delayMs);
}

function poll() {
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
}

scheduleNextPoll();

const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 5000;
let delayMs = BASE_DELAY_MS;

var getPollingUrl = function() {
    var url = new URL(window.location.href);
    url.searchParams.set('ajax', '1');
    return url.toString();
};

var scheduleNextCheck = function() {
    window.setTimeout(check, delayMs);
};

var check = function() {
    fetch(getPollingUrl(), {
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
            if (data && data.redirect) {
                window.location.href = data.redirect;
                return;
            }

            delayMs = BASE_DELAY_MS;
            scheduleNextCheck();
        })
        .catch(function(error) {
            console.error('Async task polling failed', error);
            delayMs = Math.min(Math.floor(delayMs * 1.5), MAX_DELAY_MS);
            scheduleNextCheck();
        });
};

scheduleNextCheck();

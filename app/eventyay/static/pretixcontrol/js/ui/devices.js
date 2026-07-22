/*globals gettext*/
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 5000;
let delayMs = BASE_DELAY_MS;

const credEl = document.getElementById('device_connect_credentials');
const downloadBtn = document.getElementById('device_connect_download_token');
if (credEl && downloadBtn) {
    downloadBtn.addEventListener('click', function () {
        const data = credEl.textContent;
        const blob = new Blob([data], {type: 'application/json'});
        const objectUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = downloadBtn.getAttribute('data-download-filename') || 'eventyay-device-setup.json';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(objectUrl);
    });
}

if (document.getElementById('device_connect_poll')) {
  var reloaded = false;
  var pollUrl = new URL(window.location.href);
  pollUrl.searchParams.set('ajax', 'true');
  
  function scheduleNextUpdate() {
    window.setTimeout(update, delayMs);
  }
  
  function update() {
    fetch(pollUrl, {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
      },
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('Polling request failed with status ' + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        if (data.initialized) {
          if (!reloaded) {
            reloaded = true;
            location.reload();
          }
          return;
        }
        delayMs = BASE_DELAY_MS;
        scheduleNextUpdate();
      })
      .catch(function (err) {
        console.error('device initialization polling failed:', err);
        delayMs = Math.min(Math.floor(delayMs * 1.5), MAX_DELAY_MS);
        scheduleNextUpdate();
      });
  }
  scheduleNextUpdate();
}

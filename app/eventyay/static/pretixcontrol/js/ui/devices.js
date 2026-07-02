/*globals $, gettext*/

$(function () {
    var credEl = document.getElementById('device_connect_credentials');
    var downloadBtn = document.getElementById('device_connect_download_token');
    if (credEl && downloadBtn) {
        downloadBtn.addEventListener('click', function () {
            var data = credEl.textContent;
            var blob = new Blob([data], {type: 'application/json'});
            var objectUrl = URL.createObjectURL(blob);
            var link = document.createElement('a');
            link.href = objectUrl;
            link.download = downloadBtn.getAttribute('data-download-filename') || 'eventyay-device-setup.json';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(objectUrl);
        });
    }

    if (!document.getElementById('device_connect_poll')) {
        return;
    }

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

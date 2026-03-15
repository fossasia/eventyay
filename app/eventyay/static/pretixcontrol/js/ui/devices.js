function update() {
    fetch(location.href + '?ajax=true')
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.initialized) {
                location.reload();
            } else {
                window.setTimeout(update, 500);
            }
        })
        .catch(function (err) {
            console.error('devices: poll failed', err);
            window.setTimeout(update, 500);
        });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
        window.setTimeout(update, 500);
    });
} else {
    window.setTimeout(update, 500);
}

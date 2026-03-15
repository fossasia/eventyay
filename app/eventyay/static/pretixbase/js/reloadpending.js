var intId = window.setInterval(function () {
    fetch(location.href + '?ajax=1')
        .then(function (response) { return response.text(); })
        .then(function (data) {
            if (data === '1') {
                window.clearInterval(intId);
                location.reload();
            }
        })
        .catch(function (err) {
            console.error('reloadpending: poll failed', err);
        });
}, 500);

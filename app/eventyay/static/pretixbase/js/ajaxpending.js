var check = function () {
    fetch(location.href + '&ajax=1')
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.redirect) {
                location.href = data.redirect;
            } else {
                window.setTimeout(check, 500);
            }
        })
        .catch(function (err) {
            console.error('ajaxpending: poll failed', err);
            window.setTimeout(check, 500);
        });
};
window.setTimeout(check, 500);

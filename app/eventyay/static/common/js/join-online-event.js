$(function () {
    // Shared join handler for schedule (agenda) and ticket (presale) pages.
    $(document).off('click', '.join-video-link, .join-room-btn').on('click', '.join-video-link, .join-room-btn', function (e) {
        e.preventDefault();
        var url = $(this).attr('href');

        $.ajax({
            method: 'GET',
            url: url,
            success: function (json) {
                if (json.redirect_url) {
                    window.location.href = json.redirect_url;
                } else if (json.login_url) {
                    window.location.href = json.login_url;
                }
            },
            error: function (jqXHR) {
                var loginUrl = jqXHR.responseJSON && jqXHR.responseJSON.login_url;
                if (jqXHR.status === 401 && loginUrl) {
                    window.location.href = loginUrl;
                    return;
                }

                $('body').addClass('has-join-popup');
                if (jqXHR.responseText === 'user_not_allowed') {
                    $('#join-video-popupmodal').removeAttr('hidden');
                } else if (jqXHR.responseText === 'missing_configuration') {
                    $('#join-video-popupmodal-missing-config').removeAttr('hidden');
                }
            },
        });
    });

    $('#join-online-close-button').on('click', function () {
        $('#join-video-popupmodal').attr('hidden', 'true');
        $('body').removeClass('has-join-popup');
    });

    $('#join-online-close-button-missing-config').on('click', function () {
        $('#join-video-popupmodal-missing-config').attr('hidden', 'true');
        $('body').removeClass('has-join-popup');
    });
});

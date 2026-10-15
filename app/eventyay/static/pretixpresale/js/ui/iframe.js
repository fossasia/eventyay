var inIframe = function () {
    try {
        return window.self !== window.top;
    } catch (e) {
        return true;
    }
};
if (inIframe()) {
    document.documentElement.classList.add('in-iframe');
    window.addEventListener('message', function (e) {
        if (e.data === 'pretix:back' || (e.data && e.data.type === 'pretix:back')) {
            var params = new URLSearchParams(window.location.search);
            var next = params.get('next');
            if (next && next.startsWith('/')) {
                window.location.href = next;
            } else if (window.history.length > 1) {
                window.history.back();
            } else if (document.referrer) {
                window.location.href = document.referrer;
            }
        }
    });
}


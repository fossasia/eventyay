(function () {
    if (!window.Intl || !Intl.DateTimeFormat) {
        return;
    }

    var formatter;
    try {
        formatter = new Intl.DateTimeFormat(navigator.language, {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "numeric",
        });
    } catch (error) {
        formatter = new Intl.DateTimeFormat(navigator.language, {
            year: "numeric",
            month: "numeric",
            day: "numeric",
            hour: "numeric",
            minute: "numeric",
        });
    }

    var timeZoneFormatter = new Intl.DateTimeFormat("en", {
        timeZoneName: "shortOffset",
    });
    var timeZone = timeZoneFormatter.formatToParts(new Date()).find(function (part) {
        return part.type === "timeZoneName";
    });
    document.querySelectorAll("[data-browser-timezone-label]").forEach(function (element) {
        if (timeZone && timeZone.value) {
            element.textContent = "(" + timeZone.value + ")";
        }
    });

    document.querySelectorAll("[data-browser-local-datetime]").forEach(function (element) {
        var date = new Date(element.dateTime || element.getAttribute("datetime"));
        if (Number.isNaN(date.getTime())) {
            return;
        }
        element.textContent = formatter.format(date);
        element.title = date.toString();
    });
})();

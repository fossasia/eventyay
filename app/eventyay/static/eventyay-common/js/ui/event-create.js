(function () {
    "use strict";

    function selectedActiveLanguages() {
        return Array.from(document.querySelectorAll('input[name="foundation-locales"]:checked')).map(function (input) {
            return input.value;
        });
    }

    function updateDefaultLanguageChoices() {
        var defaultLanguage = document.getElementById("id_basics-locale");
        if (!defaultLanguage) {
            return;
        }

        var activeLanguages = selectedActiveLanguages();
        var activeSet = new Set(activeLanguages);
        var firstAvailableValue = null;

        Array.from(defaultLanguage.options).forEach(function (option) {
            var isAvailable = activeSet.has(option.value);
            option.hidden = !isAvailable;
            option.disabled = !isAvailable;
            if (isAvailable && firstAvailableValue === null) {
                firstAvailableValue = option.value;
            }
        });

        if (!activeSet.has(defaultLanguage.value)) {
            defaultLanguage.value = firstAvailableValue || "";
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll('input[name="foundation-locales"]').forEach(function (input) {
            input.addEventListener("change", updateDefaultLanguageChoices);
        });
        updateDefaultLanguageChoices();
    });
})();

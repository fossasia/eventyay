(function () {
    "use strict";

    function organizerSlugOptions() {
        var data = document.getElementById("event-create-organizers");
        if (!data) {
            return {};
        }

        try {
            return JSON.parse(data.textContent);
        } catch (error) {
            console.error("Failed to parse organizer slug options.", error);
            return {};
        }
    }

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

    function updateRandomSlug(randomSlugButton) {
        var slug = document.getElementById("id_basics-slug");
        if (!slug || slug.dataset.userEdited === "true" || !randomSlugButton.dataset.rngUrl) {
            return;
        }

        slug.value = "Generating...";
        fetch(randomSlugButton.dataset.rngUrl)
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Random slug request failed.");
                }
                return response.json();
            })
            .then(function (data) {
                slug.value = data.slug;
            })
            .catch(function (error) {
                console.error("Failed to generate random event slug.", error);
                slug.value = "";
            });
    }

    function updateOrganizerSlugUrl(options, shouldRegenerateSlug) {
        var organizer = document.querySelector("#id_foundation-organizer, [name='foundation-organizer']");
        var slugPrefix = document.querySelector(".slug-widget-prefix");
        var randomSlugButton = document.getElementById("event-slug-random-generate");
        if (!organizer || !slugPrefix || !randomSlugButton) {
            return;
        }

        var selected = options[organizer.value];
        slugPrefix.textContent = selected ? selected.prefix : "";
        randomSlugButton.dataset.rngUrl = selected ? selected.rngUrl : "";
        randomSlugButton.disabled = !selected;
        if (selected && shouldRegenerateSlug && organizer.dataset.slugOrganizer !== organizer.value) {
            organizer.dataset.slugOrganizer = organizer.value;
            updateRandomSlug(randomSlugButton);
        } else if (!selected) {
            organizer.dataset.slugOrganizer = "";
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        var options = organizerSlugOptions();
        document.querySelectorAll('input[name="foundation-locales"]').forEach(function (input) {
            input.addEventListener("change", updateDefaultLanguageChoices);
        });
        var organizer = document.querySelector("#id_foundation-organizer, [name='foundation-organizer']");
        if (organizer) {
            organizer.addEventListener("change", function () {
                updateOrganizerSlugUrl(options, true);
            });
            if (window.jQuery) {
                window.jQuery(document).on("change", "#id_foundation-organizer, [name='foundation-organizer']", function () {
                    updateOrganizerSlugUrl(options, true);
                });
            }
            updateOrganizerSlugUrl(options, false);
        }
        var slug = document.getElementById("id_basics-slug");
        if (slug) {
            slug.addEventListener("input", function () {
                slug.dataset.userEdited = "true";
            });
        }
        updateDefaultLanguageChoices();
    });
})();

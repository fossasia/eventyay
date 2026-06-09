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
        var hiddenSelect = document.querySelector('select[name="foundation-locales"]');
        if (hiddenSelect) {
            return Array.from(hiddenSelect.selectedOptions).map(function (option) {
                return option.value;
            });
        }
        return Array.from(document.querySelectorAll('input[name="foundation-locales"]:checked')).map(
            function (input) {
                return input.value;
            }
        );
    }

    function isActiveLanguageControl(target) {
        if (target.matches('input[name="foundation-locales"], select[name="foundation-locales"]')) {
            return true;
        }
        var wrapper = target.closest(".multi-language-select-wrapper");
        return Boolean(wrapper && wrapper.querySelector('select[name="foundation-locales"]'));
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

    var eventI18nValues = {};
    var eventI18nRequest = null;

    function rememberEventI18nValues() {
        document.querySelectorAll(
            '#event-name-field input[name^="basics-name_"], #event-location-field textarea[name^="basics-location_"]'
        ).forEach(function (input) {
            eventI18nValues[input.name] = input.value;
        });
    }

    function updateEventI18nFields() {
        var form = document.querySelector("form");
        var eventNameField = document.getElementById("event-name-field");
        var eventLocationField = document.getElementById("event-location-field");
        var activeLanguages = selectedActiveLanguages();
        if (!form || !eventNameField || !eventLocationField || activeLanguages.length === 0) {
            return;
        }

        rememberEventI18nValues();
        var formData = new FormData(form);
        formData.delete("foundation-locales");
        activeLanguages.forEach(function (locale) {
            formData.append("foundation-locales", locale);
        });
        Object.keys(eventI18nValues).forEach(function (name) {
            if (!formData.has(name)) {
                formData.append(name, eventI18nValues[name]);
            }
        });
        formData.set("ajax", "event-i18n-fields");

        if (eventI18nRequest) {
            eventI18nRequest.abort();
        }
        var requestController = new AbortController();
        eventI18nRequest = requestController;
        eventNameField.setAttribute("aria-busy", "true");
        eventLocationField.setAttribute("aria-busy", "true");

        fetch(window.location.href, {
            method: "POST",
            body: formData,
            signal: requestController.signal,
        })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().then(function (data) {
                        throw new Error(data.error || "Event multilingual fields request failed.");
                    });
                }
                return response.json();
            })
            .then(function (data) {
                if (eventI18nRequest !== requestController) {
                    return;
                }
                var fields = new DOMParser().parseFromString(data.fields, "text/html");
                var eventNameTemplate = fields.querySelector("#event-name-field-template");
                var eventLocationTemplate = fields.querySelector("#event-location-field-template");
                if (!eventNameTemplate || !eventLocationTemplate) {
                    throw new Error("Event multilingual fields response is incomplete.");
                }
                eventNameField.replaceChildren(eventNameTemplate.content.cloneNode(true));
                eventLocationField.replaceChildren(eventLocationTemplate.content.cloneNode(true));
                eventNameField.removeAttribute("aria-busy");
                eventLocationField.removeAttribute("aria-busy");
                eventI18nRequest = null;
            })
            .catch(function (error) {
                if (error.name !== "AbortError" && eventI18nRequest === requestController) {
                    console.error("Failed to update the event multilingual fields.", error);
                    eventNameField.removeAttribute("aria-busy");
                    eventLocationField.removeAttribute("aria-busy");
                    eventI18nRequest = null;
                }
            });
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
        document.addEventListener("change", function (event) {
            if (isActiveLanguageControl(event.target)) {
                updateDefaultLanguageChoices();
                updateEventI18nFields();
            }
        });
        document.addEventListener("click", function (event) {
            var removeButton = event.target.closest('[data-role="remove-language"]');
            if (removeButton && isActiveLanguageControl(removeButton)) {
                updateDefaultLanguageChoices();
                updateEventI18nFields();
            }
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

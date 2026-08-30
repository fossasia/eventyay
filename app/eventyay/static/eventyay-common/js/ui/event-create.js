(function () {
    "use strict";

    var currentLocaleOrder = [];
    var draggedCode = null;

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

    function getCheckedLocalesFromDOM() {
        var hiddenSelect = document.querySelector('select[name="foundation-locales"], select[name="locales"]');
        if (hiddenSelect) {
            return Array.from(hiddenSelect.selectedOptions).map(function (option) {
                return option.value;
            });
        }
        return Array.from(document.querySelectorAll('input[name="foundation-locales"]:checked, input[name="locales"]:checked')).map(
            function (input) {
                return input.value;
            }
        );
    }

    function updateLocaleOrderList() {
        var checkedLocales = getCheckedLocalesFromDOM();
        var checkedSet = new Set(checkedLocales);

        currentLocaleOrder = currentLocaleOrder.filter(function (code) {
            return checkedSet.has(code);
        });

        if (currentLocaleOrder.length === 0 && checkedLocales.length > 0) {
            var initialDefaultInput = document.getElementById("id_basics-locale") || document.getElementById("id_locale");
            var initialDefault = initialDefaultInput ? initialDefaultInput.value : "";
            if (initialDefault && checkedSet.has(initialDefault)) {
                currentLocaleOrder.push(initialDefault);
            }
        }

        checkedLocales.forEach(function (code) {
            if (currentLocaleOrder.indexOf(code) === -1) {
                currentLocaleOrder.push(code);
            }
        });
    }

    function selectedActiveLanguages() {
        updateLocaleOrderList();
        return currentLocaleOrder.slice();
    }

    function isActiveLanguageControl(target) {
        if (target.matches('input[name="foundation-locales"], select[name="foundation-locales"], input[name="locales"], select[name="locales"]')) {
            return true;
        }
        var wrapper = target.closest(".multi-language-select-wrapper");
        return Boolean(wrapper && wrapper.querySelector('select[name="foundation-locales"], select[name="locales"]'));
    }

    function getLanguageLabel(code) {
        var cell = document.querySelector('.language-grid-cell input[name="foundation-locales"][value="' + code + '"], .language-grid-cell input[name="locales"][value="' + code + '"]');
        if (cell) {
            var gridCell = cell.closest('.language-grid-cell');
            if (gridCell && gridCell.dataset.languageName) {
                return gridCell.dataset.languageName;
            }
            var label = gridCell ? gridCell.querySelector('label') : null;
            if (label) {
                return label.textContent.trim();
            }
        }
        return code;
    }

    function renderLanguageBadges() {
        var badgesContainer = document.querySelector('[data-language-grid-badges]');
        if (!badgesContainer) {
            return;
        }
        badgesContainer.dataset.customBadges = "true";

        updateLocaleOrderList();
        badgesContainer.replaceChildren();

        currentLocaleOrder.forEach(function (code, index) {
            var badge = document.createElement("span");
            badge.className = "language-grid-badge" + (index === 0 ? " is-default-language" : "");
            badge.draggable = true;
            badge.dataset.code = code;
            badge.tabIndex = 0;
            badge.setAttribute("role", "button");
            var labelText = getLanguageLabel(code);
            badge.setAttribute(
                "aria-label",
                labelText + (index === 0 ? " (Default language)" : ". Click or press Space to set as default language.")
            );
            badge.setAttribute("title", index === 0 ? "Default language" : "Click or press Space/Arrow keys to reorder/set as default");

            var handle = document.createElement("span");
            handle.className = "drag-handle";
            handle.textContent = "⠿";
            badge.appendChild(handle);

            var textSpan = document.createElement("span");
            textSpan.textContent = labelText;
            badge.appendChild(textSpan);

            badge.addEventListener("click", function (e) {
                if (index !== 0) {
                    var fromIndex = currentLocaleOrder.indexOf(code);
                    if (fromIndex !== -1) {
                        currentLocaleOrder.splice(fromIndex, 1);
                        currentLocaleOrder.unshift(code);
                        syncLocaleOrder();
                        updateEventI18nFields();
                    }
                }
            });

            badge.addEventListener("keydown", function (e) {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    if (index !== 0) {
                        var fromIndex = currentLocaleOrder.indexOf(code);
                        if (fromIndex !== -1) {
                            currentLocaleOrder.splice(fromIndex, 1);
                            currentLocaleOrder.unshift(code);
                            syncLocaleOrder();
                            updateEventI18nFields();
                        }
                    }
                } else if (e.key === "ArrowLeft" && index > 0) {
                    e.preventDefault();
                    var prevCode = currentLocaleOrder[index - 1];
                    currentLocaleOrder[index - 1] = code;
                    currentLocaleOrder[index] = prevCode;
                    syncLocaleOrder();
                    updateEventI18nFields();
                } else if (e.key === "ArrowRight" && index < currentLocaleOrder.length - 1) {
                    e.preventDefault();
                    var nextCode = currentLocaleOrder[index + 1];
                    currentLocaleOrder[index + 1] = code;
                    currentLocaleOrder[index] = nextCode;
                    syncLocaleOrder();
                    updateEventI18nFields();
                }
            });

            badge.addEventListener("dragstart", function (e) {
                draggedCode = code;
                badge.classList.add("dragging");
                e.dataTransfer.effectAllowed = "move";
                e.dataTransfer.setData("text/plain", code);
            });

            badge.addEventListener("dragend", function () {
                draggedCode = null;
                badge.classList.remove("dragging");
            });

            badge.addEventListener("dragover", function (e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
            });

            badge.addEventListener("drop", function (e) {
                e.preventDefault();
                if (!draggedCode || draggedCode === code) {
                    return;
                }
                var fromIndex = currentLocaleOrder.indexOf(draggedCode);
                var toIndex = currentLocaleOrder.indexOf(code);
                if (fromIndex !== -1 && toIndex !== -1) {
                    currentLocaleOrder.splice(fromIndex, 1);
                    currentLocaleOrder.splice(toIndex, 0, draggedCode);
                    syncLocaleOrder();
                    updateEventI18nFields();
                }
            });

            badgesContainer.appendChild(badge);
        });

        var countLabel = document.querySelector('[data-language-grid-count]');
        if (countLabel) {
            if (currentLocaleOrder.length === 0) {
                countLabel.style.display = "";
            } else {
                countLabel.style.display = "none";
            }
        }
    }

    function syncLocaleOrder() {
        var hiddenLocaleInput = document.getElementById("id_basics-locale") || document.getElementById("id_locale");
        updateLocaleOrderList();
        if (hiddenLocaleInput) {
            var checkedLocales = getCheckedLocalesFromDOM();
            hiddenLocaleInput.value =
                currentLocaleOrder[0] || hiddenLocaleInput.value || checkedLocales[0] || "en";
        }
        renderLanguageBadges();
    }

    function syncFoundationLocalesOnSubmit(form) {
        if (!form) return;
        updateLocaleOrderList();
        var localesToSubmit = currentLocaleOrder.length ? currentLocaleOrder : getCheckedLocalesFromDOM();
        if (localesToSubmit.length === 0) {
            return;
        }
        var checkboxes = form.querySelectorAll('input[type="checkbox"][name="foundation-locales"]');
        checkboxes.forEach(function (input) {
            input.removeAttribute("name");
        });
        var select = form.querySelector('select[name="foundation-locales"]');
        if (select) {
            select.removeAttribute("name");
        }
        var oldContainer = document.getElementById("event-create-locales-order-container");
        if (oldContainer) {
            oldContainer.remove();
        }
        var container = document.createElement("div");
        container.id = "event-create-locales-order-container";
        container.style.display = "none";
        localesToSubmit.forEach(function (code) {
            var hidden = document.createElement("input");
            hidden.type = "hidden";
            hidden.name = "foundation-locales";
            hidden.value = code;
            container.appendChild(hidden);
        });
        form.appendChild(container);
        var hiddenLocaleInput = document.getElementById("id_basics-locale") || document.getElementById("id_locale");
        if (hiddenLocaleInput && !hiddenLocaleInput.value) {
            hiddenLocaleInput.value = localesToSubmit[0] || "en";
        }
    }

    function updateDefaultLanguageChoices() {
        syncLocaleOrder();
    }

    var eventI18nValues = {};
    var eventI18nRequest = null;

    function rememberEventI18nValues() {
        document.querySelectorAll(
            '#event-name-field input[name^="basics-name_"], #event-location-field textarea[name^="basics-location_"], #event-name-field input[name^="name_"]'
        ).forEach(function (input) {
            eventI18nValues[input.name] = input.value;
        });
    }

    function updateEventI18nFields() {
        var form = document.querySelector("form");
        var eventNameField = document.getElementById("event-name-field");
        var eventLocationField = document.getElementById("event-location-field");
        var activeLanguages = selectedActiveLanguages();
        if (!form || !eventNameField || activeLanguages.length === 0) {
            return;
        }

        rememberEventI18nValues();
        var formData = new FormData(form);
        formData.delete("foundation-locales");
        formData.delete("locales");
        activeLanguages.forEach(function (locale) {
            formData.append("foundation-locales", locale);
            formData.append("locales", locale);
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
        if (eventLocationField) {
            eventLocationField.setAttribute("aria-busy", "true");
        }

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
                if (!eventNameTemplate) {
                    throw new Error("Event multilingual fields response is incomplete.");
                }
                eventNameField.replaceChildren(eventNameTemplate.content.cloneNode(true));
                if (eventLocationField && eventLocationTemplate) {
                    eventLocationField.replaceChildren(eventLocationTemplate.content.cloneNode(true));
                    eventLocationField.removeAttribute("aria-busy");
                } else if (eventLocationField) {
                    eventLocationField.removeAttribute("aria-busy");
                }
                eventNameField.removeAttribute("aria-busy");
                eventI18nRequest = null;
            })
            .catch(function (error) {
                if (error.name !== "AbortError" && eventI18nRequest === requestController) {
                    console.error("Failed to update the event multilingual fields.", error);
                    eventNameField.removeAttribute("aria-busy");
                    if (eventLocationField) {
                        eventLocationField.removeAttribute("aria-busy");
                    }
                    eventI18nRequest = null;
                }
            });
    }

    function getSlugInput() {
        return document.getElementById("id_basics-slug") || document.querySelector('[name="basics-slug"]') || document.getElementById("id_slug") || document.querySelector('[name="slug"]');
    }

    function updateRandomSlug(randomSlugButton, force) {
        var slug = getSlugInput();
        if (!slug || !randomSlugButton.dataset.rngUrl || randomSlugButton.dataset.generating === "true") {
            return;
        }
        if (!force && slug.dataset.userEdited === "true") {
            return;
        }

        randomSlugButton.dataset.generating = "true";
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
                delete slug.dataset.userEdited;
            })
            .catch(function (error) {
                console.error("Failed to generate random event slug.", error);
                slug.value = "";
            })
            .finally(function () {
                delete randomSlugButton.dataset.generating;
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
        var form = document.querySelector("form");
        if (form) {
            form.addEventListener("submit", function () {
                syncLocaleOrder();
                syncFoundationLocalesOnSubmit(form);
            });
        }
        document.addEventListener("change", function (event) {
            if (isActiveLanguageControl(event.target)) {
                syncLocaleOrder();
                updateEventI18nFields();
            }
        });
        document.addEventListener("click", function (event) {
            var removeButton = event.target.closest('[data-role="remove-language"]');
            if (removeButton && isActiveLanguageControl(removeButton)) {
                syncLocaleOrder();
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
        var slug = getSlugInput();
        if (slug) {
            slug.addEventListener("input", function () {
                slug.dataset.userEdited = "true";
            });
        }
        var randomSlugButton = document.getElementById("event-slug-random-generate");
        if (randomSlugButton) {
            randomSlugButton.addEventListener("click", function () {
                updateRandomSlug(randomSlugButton, true);
            });
        }
        syncLocaleOrder();
        updateEventI18nFields();
    });
})();


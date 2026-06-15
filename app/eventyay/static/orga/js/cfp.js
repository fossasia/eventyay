document
    .querySelectorAll(".cfp-option-table .require input")
    .forEach((element) => {
        element.addEventListener("click", (ev) => {
            if (ev.target.checked) {
                ev.target.parentElement.parentElement.parentElement.parentElement.querySelector(
                    ".request input",
                ).checked = true
            }
        })
    });

document.addEventListener("DOMContentLoaded", () => {
    const contentLocaleToggle = document.querySelector("tr[dragsort-id='content_locale'] .toggle-switch[data-field-id] input[type='checkbox']");
    const settingsBtns = document.querySelectorAll(".content-locale-settings-btn");
    const dialog = document.getElementById("content-locale-dialog");
    const cancelBtn = document.getElementById("content-locale-dialog-cancel");
    const saveBtn = document.getElementById("content-locale-dialog-save");

    if (dialog) {
        let initialCheckedStates = [];
        let initialToggleState = false;
        let isRestoring = false;

        const isToggleChecked = () => {
            return contentLocaleToggle ? contentLocaleToggle.checked : false;
        };

        const resetSearch = () => {
            const searchInput = document.getElementById("content-locale-search");
            if (searchInput) {
                searchInput.value = "";
            }
            dialog.querySelectorAll(".content-locale-checkbox-list .checkbox").forEach((div) => {
                div.classList.remove("d-none");
            });
        };

        const openDialog = (triggeredByToggle = false) => {
            resetSearch();
            initialToggleState = triggeredByToggle ? false : isToggleChecked();
            initialCheckedStates = Array.from(dialog.querySelectorAll(".content-locale-checkbox")).map(checkbox => ({
                checkbox: checkbox,
                checked: checkbox.checked
            }));

            if (typeof dialog.showModal === "function") {
                dialog.showModal();
            } else {
                dialog.setAttribute("open", "true");
            }
        };

        const closeDialog = () => {
            resetSearch();
            if (typeof dialog.close === "function") {
                dialog.close();
            } else {
                dialog.removeAttribute("open");
            }
        };

        const cancelDialog = () => {
            initialCheckedStates.forEach(item => {
                item.checkbox.checked = item.checked;
            });
            isRestoring = true;
            if (contentLocaleToggle && contentLocaleToggle.checked !== initialToggleState) {
                contentLocaleToggle.checked = initialToggleState;
                contentLocaleToggle.dispatchEvent(new Event('change', { bubbles: true }));
            }
            isRestoring = false;
            if (initialToggleState) {
                settingsBtns.forEach(btn => btn.classList.remove("hidden"));
            } else {
                settingsBtns.forEach(btn => btn.classList.add("hidden"));
            }
            closeDialog();
        };

        if (contentLocaleToggle) {
            contentLocaleToggle.addEventListener("change", (ev) => {
                if (isRestoring) return;
                if (ev.target.checked) {
                    openDialog(true);
                    settingsBtns.forEach(btn => btn.classList.remove("hidden"));
                } else {
                    settingsBtns.forEach(btn => btn.classList.add("hidden"));
                }
            });
        }

        settingsBtns.forEach(btn => {
            btn.addEventListener("click", () => openDialog(false));
        });

        if (cancelBtn) {
            cancelBtn.addEventListener("click", cancelDialog);
        }

        if (saveBtn) {
            saveBtn.addEventListener("click", closeDialog);
        }

        const searchInput = document.getElementById("content-locale-search");
        if (searchInput) {
            searchInput.addEventListener("input", (ev) => {
                const query = ev.target.value.toLowerCase().trim();
                dialog.querySelectorAll(".content-locale-checkbox-list .checkbox").forEach((div) => {
                    const labelText = div.textContent.toLowerCase();
                    if (labelText.includes(query)) {
                        div.classList.remove("d-none");
                    } else {
                        div.classList.add("d-none");
                    }
                });
            });
        }

        dialog.addEventListener("cancel", (event) => {
            event.preventDefault();
            cancelDialog();
        });

        dialog.addEventListener("click", (event) => {
            if (event.target === dialog) {
                cancelDialog();
            }
        });

        if (dialog.querySelector(".alert-danger")) {
            openDialog();
        }
    }
});

document.addEventListener("DOMContentLoaded", () => {
    const settingsButton = document.querySelector(".profile-picture-settings-button")
    const settingsPopover = document.querySelector(".profile-picture-settings-popover")
    if (!settingsButton || !settingsPopover) return

    const closePopover = () => {
        settingsPopover.classList.add("d-none")
        settingsButton.setAttribute("aria-expanded", "false")
    }

    const openPopover = () => {
        settingsPopover.classList.remove("d-none")
        settingsPopover.style.visibility = "hidden"

        const buttonRect = settingsButton.getBoundingClientRect()
        const popoverRect = settingsPopover.getBoundingClientRect()
        const margin = 8
        const left = Math.min(
            Math.max(margin, buttonRect.right - popoverRect.width),
            window.innerWidth - popoverRect.width - margin,
        )
        const spaceAbove = buttonRect.top - popoverRect.height - margin
        const opensAbove = spaceAbove >= margin
        const top = opensAbove ? spaceAbove : buttonRect.bottom + margin

        settingsPopover.style.left = `${left}px`
        settingsPopover.style.top = `${top}px`
        settingsPopover.dataset.placement = opensAbove ? "above" : "below"
        settingsPopover.style.visibility = ""
        settingsButton.setAttribute("aria-expanded", "true")
    }

    settingsButton.addEventListener("click", (event) => {
        event.stopPropagation()
        if (settingsPopover.classList.contains("d-none")) {
            openPopover()
        } else {
            closePopover()
        }
    })

    settingsPopover.addEventListener("click", (event) => event.stopPropagation())
    document.addEventListener("click", closePopover)
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !settingsPopover.classList.contains("d-none")) {
            closePopover()
            settingsButton.focus()
        }
    })
    window.addEventListener("resize", closePopover)
    window.addEventListener("scroll", closePopover, true)
})

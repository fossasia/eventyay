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
    const contentLocaleToggles = document.querySelectorAll("tr[dragsort-id='content_locale'] .toggle-switch[data-field-id] input[type='checkbox']");
    const settingsBtns = document.querySelectorAll(".content-locale-settings-btn");
    const dialog = document.getElementById("content-locale-dialog");
    const cancelBtn = document.getElementById("content-locale-dialog-cancel");
    const saveBtn = document.getElementById("content-locale-dialog-save");

    if (dialog) {
        let initialCheckedStates = [];
        let initialToggleState = false;

        const isToggleChecked = () => {
            const firstToggle = document.querySelector("tr[dragsort-id='content_locale'] .toggle-switch[data-field-id] input[type='checkbox']");
            return firstToggle ? firstToggle.checked : false;
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
            contentLocaleToggles.forEach(toggle => {
                if (toggle.checked !== initialToggleState) {
                    toggle.checked = initialToggleState;
                    toggle.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
            if (initialToggleState) {
                settingsBtns.forEach(btn => btn.classList.remove("hidden"));
            } else {
                settingsBtns.forEach(btn => btn.classList.add("hidden"));
            }
            closeDialog();
        };

        contentLocaleToggles.forEach(toggle => {
            toggle.addEventListener("change", (ev) => {
                contentLocaleToggles.forEach(t => {
                    t.checked = ev.target.checked;
                });
                if (ev.target.checked) {
                    openDialog(true);
                    settingsBtns.forEach(btn => btn.classList.remove("hidden"));
                } else {
                    settingsBtns.forEach(btn => btn.classList.add("hidden"));
                }
            });
        });

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

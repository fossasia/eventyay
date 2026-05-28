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
    const contentLocaleToggle = document.querySelector("tr[dragsort-id='content_locale'] .toggle-switch input[type='checkbox']");
    const settingsBtn = document.querySelector(".content-locale-settings-btn");
    const dialog = document.getElementById("content-locale-dialog");
    const cancelBtn = document.getElementById("content-locale-dialog-cancel");
    const saveBtn = document.getElementById("content-locale-dialog-save");

    if (contentLocaleToggle && dialog) {
        let initialCheckedStates = [];

        const openDialog = () => {
            initialCheckedStates = Array.from(dialog.querySelectorAll("input[name='settings-content_locales']")).map(checkbox => ({
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
            closeDialog();
        };

        contentLocaleToggle.addEventListener("change", (ev) => {
            if (ev.target.checked) {
                openDialog();
                if (settingsBtn) settingsBtn.classList.remove("hidden");
            } else {
                if (settingsBtn) settingsBtn.classList.add("hidden");
            }
        });

        if (settingsBtn) {
            settingsBtn.addEventListener("click", openDialog);
        }

        if (cancelBtn) {
            cancelBtn.addEventListener("click", cancelDialog);
        }

        if (saveBtn) {
            saveBtn.addEventListener("click", closeDialog);
        }
    }
});

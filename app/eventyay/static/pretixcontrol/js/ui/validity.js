/**
 * Toggle visibility of ticket validity fixed-date fields
 * based on the selected validity mode.
 *
 * Loaded on the product edit page (pretixcontrol/item/index.html).
 */
document.addEventListener("DOMContentLoaded", function () {
    const modeField = document.getElementById("id_validity_mode");
    const fixedFields = document.getElementById("validity-fixed-fields");
    const statusFixed = document.getElementById("validity-status");
    const statusDefault = document.getElementById("validity-status-default");

    if (!modeField || !fixedFields) {
        return;
    }

    function toggle() {
        const isFixed = modeField.value === "fixed";
        fixedFields.style.display = isFixed ? "" : "none";
        if (statusFixed) {
            statusFixed.style.display = isFixed ? "" : "none";
        }
        if (statusDefault) {
            statusDefault.style.display = isFixed ? "none" : "";
        }
    }

    modeField.addEventListener("change", toggle);
    toggle();
});

/**
 * Toggle visibility of ticket validity fixed-date fields
 * based on the selected validity mode.
 *
 * Loaded on the product edit page (pretixcontrol/item/index.html).
 */
function initValidity() {
    const modeField = document.getElementById('id_validity_mode');
    const fixedFields = document.getElementById('validity-fixed-fields');
    const statusFixed = document.getElementById('validity-status');
    const statusDefault = document.getElementById('validity-status-default');

    if (!modeField || !fixedFields) {
        return;
    }

    function toggle() {
        const isFixed = modeField.value === 'fixed';
        fixedFields.hidden = !isFixed;
        if (statusFixed) {
            statusFixed.hidden = !isFixed;
        }
        if (statusDefault) {
            statusDefault.hidden = isFixed;
        }
    }

    modeField.addEventListener('change', toggle);
    toggle();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initValidity);
} else {
    initValidity();
}

const updateDelimiterVisibility = (panel) => {
    const exportFormatRadios = panel.querySelectorAll("input[type='radio'][name$='-export_format']")
    const delimiterGroup = panel.querySelector("[data-delimiter-group]")
    if (!delimiterGroup || !exportFormatRadios.length) {
        return
    }
    const selected = Array.from(exportFormatRadios).find((radio) => radio.checked)
    delimiterGroup.style.display = selected?.value === "csv" ? "block" : "none"
}

const updateExportPanelVisibility = (wrapper, selectedTarget) => {
    wrapper.querySelectorAll("[data-export-panel]").forEach((panel) => {
        const isActive = panel.dataset.exportPanel === selectedTarget
        panel.style.display = isActive ? "block" : "none"
        if (isActive) {
            updateDelimiterVisibility(panel)
        }
    })
}

const handleSelectAll = (selectAllCheckbox) => {
    const panel = selectAllCheckbox.closest("[data-export-panel]")
    if (!panel) {
        return
    }
    panel.querySelectorAll("input[type='checkbox']:not([data-select-all])").forEach((checkbox) => {
        checkbox.checked = selectAllCheckbox.checked
    })
}

const updateSelectAllState = (panel) => {
    const selectAllCheckbox = panel.querySelector("[data-select-all]")
    if (!selectAllCheckbox) {
        return
    }
    const checkboxes = Array.from(panel.querySelectorAll("input[type='checkbox']:not([data-select-all])"))
    if (checkboxes.length === 0) {
        return
    }
    const allChecked = checkboxes.every((checkbox) => checkbox.checked)
    selectAllCheckbox.checked = allChecked
}

const addImportExportSettingsHooks = () => {
    const wrapper = document.querySelector("#unified-export")
    if (!wrapper) {
        return
    }

    const targetSelect = wrapper.querySelector("[data-export-target-select]")
    if (!targetSelect) {
        return
    }

    // Initialize visibility
    const initialTarget = wrapper.dataset.exportTarget || targetSelect.value || "speaker"
    targetSelect.value = initialTarget
    // Fallback if initialTarget was invalid (setting .value to an invalid value clears it)
    const selectedTarget = targetSelect.value || targetSelect.options[0]?.value || "speaker"
    targetSelect.value = selectedTarget
    updateExportPanelVisibility(wrapper, selectedTarget)

    // Handle target change
    targetSelect.addEventListener("change", (event) => {
        const target = event.target.value
        updateExportPanelVisibility(wrapper, target)
    })

    // Handle delimiter visibility change
    wrapper.querySelectorAll("[data-export-panel]").forEach((panel) => {
        panel.querySelectorAll("input[type='radio'][name$='-export_format']").forEach((radio) => {
            radio.addEventListener("change", () => updateDelimiterVisibility(panel))
        })
        // Initialize select all state for each panel
        updateSelectAllState(panel)
    })

    // Delegated event listener for checkboxes (Select All logic)
    wrapper.addEventListener("change", (event) => {
        const target = event.target
        if (target.hasAttribute("data-select-all")) {
            handleSelectAll(target)
        } else if (target.type === "checkbox") {
            const panel = target.closest("[data-export-panel]")
            if (panel) {
                updateSelectAllState(panel)
            }
        }
    })
}

onReady(addImportExportSettingsHooks)

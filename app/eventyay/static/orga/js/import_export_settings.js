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

const addImportExportSettingsHooks = () => {
    const wrapper = document.querySelector("#unified-export")
    if (!wrapper) {
        return
    }

    const targetSelect = wrapper.querySelector("[data-export-target-select]")
    if (!targetSelect) {
        return
    }

    const initialTarget = wrapper.dataset.exportTarget || targetSelect.value || "speaker"
    targetSelect.value = initialTarget
    updateExportPanelVisibility(wrapper, initialTarget)

    targetSelect.addEventListener("change", (event) => {
        const target = event.target.value
        updateExportPanelVisibility(wrapper, target)
    })

    wrapper.querySelectorAll("[data-export-panel]").forEach((panel) => {
        panel.querySelectorAll("input[type='radio'][name$='-export_format']").forEach((radio) => {
            radio.addEventListener("change", () => updateDelimiterVisibility(panel))
        })
    })
}

onReady(addImportExportSettingsHooks)

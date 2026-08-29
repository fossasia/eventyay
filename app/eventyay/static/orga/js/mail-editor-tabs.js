const getActiveLocale = () => {
    const activeLanguageTab = document.querySelector(".mail-language-tab[aria-selected='true']")
    if (activeLanguageTab) return activeLanguageTab.dataset.locale

    const message = document.querySelector("#id_text textarea[lang]")
    return message ? message.lang : ""
}

const showPreviewLocale = (panel, locale) => {
    const previews = panel.querySelectorAll(".mail-preview[lang]")
    previews.forEach((preview) => {
        preview.hidden = Boolean(locale && preview.lang !== locale)
    })
}

const initMailEditorTabs = () => {
    const wrapper = document.querySelector(".mail-editor-tabs")
    if (!wrapper) return

    const buttons = [...wrapper.querySelectorAll("[data-mail-editor-mode]")]
    const editPanel = wrapper.querySelector("#mail-message-edit")
    const previewPanel = wrapper.querySelector("#mail-message-preview")
    if (!buttons.length || !editPanel || !previewPanel) return

    const selectMode = (mode) => {
        const previewSelected = mode === "preview"
        editPanel.hidden = previewSelected
        previewPanel.hidden = !previewSelected
        showPreviewLocale(previewPanel, getActiveLocale())

        buttons.forEach((button) => {
            const active = button.dataset.mailEditorMode === mode
            button.classList.toggle("active", active)
            button.setAttribute("aria-selected", active ? "true" : "false")
            button.tabIndex = active ? 0 : -1
        })
        wrapper.dataset.mailEditorActive = mode
    }

    buttons.forEach((button, index) => {
        button.addEventListener("click", () => selectMode(button.dataset.mailEditorMode))
        button.addEventListener("keydown", (event) => {
            const offset = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0
            if (!offset) return
            event.preventDefault()
            const next = buttons[(index + offset + buttons.length) % buttons.length]
            selectMode(next.dataset.mailEditorMode)
            next.focus()
        })
    })

    document.addEventListener("mail-language-change", (event) => {
        showPreviewLocale(previewPanel, event.detail.locale)
    })
    selectMode("edit")
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initMailEditorTabs)
} else {
    initMailEditorTabs()
}

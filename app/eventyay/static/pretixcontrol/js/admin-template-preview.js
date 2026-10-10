const PREVIEW_SELECTOR = "textarea[data-template-preview]"

const lockEditor = (textarea) => {
    const editor = textarea.__eventyayTiptapEditor
    if (!editor) return false
    editor.setEditable(false)
    const wrapper = textarea.closest("[data-tiptap-wrapper]")
    wrapper?.classList.add("tiptap-readonly")
    wrapper?.querySelectorAll(".tiptap-toolbar button").forEach((button) => {
        button.disabled = true
    })
    return true
}

const lockAll = () => {
    const pending = Array.from(document.querySelectorAll(PREVIEW_SELECTOR)).filter(
        (textarea) => !textarea.dataset.previewLocked,
    )
    pending.forEach((textarea) => {
        if (lockEditor(textarea)) {
            textarea.dataset.previewLocked = "true"
        }
    })
    return pending.every((textarea) => textarea.dataset.previewLocked)
}

const initTemplatePreview = () => {
    if (lockAll()) return
    const observer = new MutationObserver(() => {
        if (lockAll()) observer.disconnect()
    })
    observer.observe(document.body, { childList: true, subtree: true })
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTemplatePreview)
} else {
    initTemplatePreview()
}

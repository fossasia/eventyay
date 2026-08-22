/**
 * Dashboard internal note — save handler.
 *
 * Sends the note content to the server via fetch() when the save button
 * is clicked. Shows a brief status message on success or error.
 */
document.addEventListener("DOMContentLoaded", () => {
    const textarea = document.getElementById("dashboard-internal-note")
    const saveBtn = document.getElementById("save-internal-note")
    const statusEl = document.getElementById("note-status")

    if (!textarea || !saveBtn) return

    const saveUrl = textarea.dataset.saveUrl
    if (!saveUrl) return

    saveBtn.addEventListener("click", () => {
        const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value
            || document.cookie.split("; ").find((c) => c.startsWith("csrftoken="))?.split("=")[1]
            || ""

        const formData = new FormData()
        formData.append("note", textarea.value)

        saveBtn.disabled = true
        if (statusEl) statusEl.textContent = ""

        fetch(saveUrl, {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
            body: formData,
        })
            .then((response) => {
                if (!response.ok) throw new Error(response.statusText)
                return response.json()
            })
            .then(() => {
                if (statusEl) statusEl.textContent = "✓ Saved"
                setTimeout(() => {
                    if (statusEl) statusEl.textContent = ""
                }, 3000)
            })
            .catch((err) => {
                if (statusEl) {
                    statusEl.textContent = "Error: " + err.message
                    statusEl.classList.add("text-danger")
                    statusEl.classList.remove("text-muted")
                }
            })
            .finally(() => {
                saveBtn.disabled = false
            })
    })
})

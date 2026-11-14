/* Speakers list: confirm before sending or resending a speaker voucher. */

const dialog = document.getElementById("speaker-voucher-row-confirm")
const form = document.getElementById("speaker-voucher-row-form")
const speakerLabel = document.getElementById("speaker-voucher-row-speaker")
const usedLabel = document.getElementById("speaker-voucher-row-used")
const confirmBtn = document.getElementById("speaker-voucher-row-confirm-btn")
const title = document.getElementById("speaker-voucher-row-confirm-title")

let pendingUrl = ""

document.querySelectorAll(".speaker-voucher-action").forEach((button) => {
    button.addEventListener("click", () => {
        pendingUrl = button.dataset.url || ""
        const action = button.dataset.action || "send"
        if (speakerLabel) speakerLabel.textContent = button.dataset.speaker || ""
        if (usedLabel) usedLabel.textContent = action === "resend" ? "0" : "1"
        if (title) {
            title.textContent = action === "resend" ? "Resend speaker voucher?" : "Send speaker voucher?"
        }
        if (confirmBtn) {
            confirmBtn.textContent = action === "resend" ? "Resend" : "Send"
        }
        dialog?.showModal()
    })
})

document.getElementById("speaker-voucher-row-cancel")?.addEventListener("click", () => {
    dialog?.close()
    pendingUrl = ""
})

confirmBtn?.addEventListener("click", () => {
    if (!form || !pendingUrl) return
    form.action = pendingUrl
    dialog?.close()
    form.requestSubmit()
})

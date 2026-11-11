/* Speaker Vouchers settings page: gate Send until settings are saved, confirm before bulk send. */

const settingsForm = document.getElementById("speaker-voucher-settings-form")
const sendBtn = document.getElementById("speaker-voucher-send-btn")
const sendForm = document.getElementById("speaker-voucher-send-form")
const sendHint = document.getElementById("speaker-voucher-send-hint")
const dirtyHint = document.getElementById("speaker-voucher-dirty-hint")
const sendStatus = document.getElementById("speaker-voucher-send-status")
const confirmDialog = document.getElementById("speaker-voucher-confirm-dialog")
const previewDialog = document.getElementById("speaker-voucher-email-preview")

const hintText = (element) => {
    if (!element) return ""
    const textNode = element.querySelector(".speaker-voucher-hint-text")
    return (textNode ? textNode.textContent : element.textContent).trim()
}

if (settingsForm && sendBtn) {
    const savedEnabled = settingsForm.dataset.savedEnabled === "true"
    const savedTag = settingsForm.dataset.savedVoucherTag || ""
    const enabledInput = settingsForm.querySelector("#id_enabled")
    const tagInput = settingsForm.querySelector("#id_voucher_tag")

    const currentEnabled = () => Boolean(enabledInput && enabledInput.checked)
    const currentTag = () => (tagInput ? tagInput.value : "")
    const isDirty = () => currentEnabled() !== savedEnabled || currentTag() !== savedTag

    sendBtn.dataset.serverBlocked = sendBtn.disabled ? "true" : "false"

    const announceSendStatus = (message) => {
        if (!sendStatus) return
        // Clear first so repeated identical messages are still announced.
        sendStatus.textContent = ""
        if (message) {
            sendStatus.textContent = message
        }
    }

    const refreshSendButton = () => {
        const dirty = isDirty()
        const serverBlocked = sendBtn.dataset.serverBlocked === "true"
        const shouldDisable = dirty || serverBlocked
        sendBtn.disabled = shouldDisable
        sendBtn.setAttribute("aria-disabled", shouldDisable ? "true" : "false")

        if (dirtyHint) {
            dirtyHint.classList.toggle("d-none", !dirty)
        }
        if (sendHint) {
            // Server blocker only when form is clean; dirty hint takes priority.
            sendHint.classList.toggle("d-none", dirty || !serverBlocked)
        }

        if (dirty) {
            announceSendStatus(hintText(dirtyHint))
        } else if (serverBlocked) {
            announceSendStatus(hintText(sendHint))
        } else {
            announceSendStatus("")
        }
    }

    enabledInput?.addEventListener("change", refreshSendButton)
    tagInput?.addEventListener("change", refreshSendButton)
    refreshSendButton()

    sendBtn.addEventListener("click", () => {
        if (sendBtn.disabled) return
        confirmDialog?.showModal()
    })

    document.getElementById("speaker-voucher-confirm-cancel")?.addEventListener("click", () => {
        confirmDialog?.close()
    })

    document.getElementById("speaker-voucher-confirm-send")?.addEventListener("click", () => {
        confirmDialog?.close()
        sendBtn.disabled = true
        sendForm?.requestSubmit()
    })

    document.getElementById("speaker-voucher-preview-btn")?.addEventListener("click", () => {
        previewDialog?.showModal()
    })
    document.getElementById("speaker-voucher-preview-close")?.addEventListener("click", () => {
        previewDialog?.close()
    })
}

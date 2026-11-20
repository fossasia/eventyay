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

const INFO_GAP = 6
const HIDE_DELAY_MS = 120

const placeInfoBox = (trigger, box) => {
    const rect = trigger.getBoundingClientRect()
    const boxWidth = Math.min(280, window.innerWidth * 0.7)
    let left = rect.right - boxWidth
    left = Math.max(8, Math.min(left, window.innerWidth - boxWidth - 8))

    box.style.left = `${left}px`
    box.style.right = "auto"
    box.style.top = `${rect.bottom + INFO_GAP}px`
    box.style.bottom = "auto"

    // Flip above the trigger when there is not enough room below.
    box.classList.add("is-visible")
    const boxRect = box.getBoundingClientRect()
    if (boxRect.bottom > window.innerHeight - 8) {
        box.style.top = "auto"
        box.style.bottom = `${window.innerHeight - rect.top + INFO_GAP}px`
        box.classList.add("is-above")
    } else {
        box.classList.remove("is-above")
    }
}

document.querySelectorAll(".speaker-voucher-info-wrapper").forEach((wrapper) => {
    const trigger = wrapper.querySelector(".speaker-voucher-info")
    const box = wrapper.querySelector(".speaker-voucher-info-box")
    if (!trigger || !box) return

    let hideTimer = null

    const show = () => {
        if (hideTimer) {
            clearTimeout(hideTimer)
            hideTimer = null
        }
        placeInfoBox(trigger, box)
    }

    const hide = () => {
        hideTimer = setTimeout(() => {
            box.classList.remove("is-visible", "is-above")
            box.style.top = ""
            box.style.bottom = ""
            box.style.left = ""
            box.style.right = ""
            hideTimer = null
        }, HIDE_DELAY_MS)
    }

    wrapper.addEventListener("mouseenter", show)
    wrapper.addEventListener("mouseleave", hide)
    wrapper.addEventListener("focusin", show)
    wrapper.addEventListener("focusout", (event) => {
        if (!wrapper.contains(event.relatedTarget)) hide()
    })
    box.addEventListener("mouseenter", show)
    box.addEventListener("mouseleave", hide)
})

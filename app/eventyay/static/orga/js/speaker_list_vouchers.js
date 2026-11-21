/* Speakers list: voucher send confirm and bulk selection. */

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
        if (speakerLabel) speakerLabel.textContent = truncateName(button.dataset.speaker || "")
        if (usedLabel) usedLabel.textContent = "1"
        if (title) title.textContent = "Send speaker voucher?"
        if (confirmBtn) confirmBtn.textContent = "Send"
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

function gettext(msgid) {
    return typeof window.gettext === "function" ? window.gettext(msgid) : msgid
}

function ngettext(singular, plural, count) {
    if (typeof window.ngettext === "function") {
        return window.ngettext(singular, plural, count)
    }
    return count === 1 ? singular : plural
}

function withCount(template, count) {
    return template.replace("%(count)s", String(count)).replace("{count}", String(count))
}

function truncateName(name, max = 42) {
    const value = String(name || "").trim()
    if (value.length <= max) return value
    return `${value.slice(0, max - 1)}…`
}

const selectAll = document.getElementById("select-all-speakers")
const checkboxes = document.querySelectorAll(".speaker-checkbox")
const selectedCount = document.getElementById("speakers-selected-count")
const bulkSendBtn = document.getElementById("speaker-bulk-send-btn")
const bulkForm = document.getElementById("speaker-bulk-voucher-form")
const bulkDialog = document.getElementById("speaker-voucher-bulk-confirm")
const bulkSummary = document.getElementById("speaker-voucher-bulk-summary")
const bulkGroups = document.getElementById("speaker-voucher-bulk-groups")
const bulkSkipped = document.getElementById("speaker-voucher-bulk-skipped")
const bulkEmpty = document.getElementById("speaker-voucher-bulk-empty")
const bulkPreview = document.getElementById("speaker-voucher-bulk-preview")
const bulkConfirmBtn = document.getElementById("speaker-voucher-bulk-confirm-btn")
const bulkConfirmLabel = document.getElementById("speaker-voucher-bulk-confirm-label")

const selectedCheckboxes = () => Array.from(checkboxes).filter((cb) => cb.checked)

const refreshSelectionUi = () => {
    const count = selectedCheckboxes().length
    if (selectedCount) {
        selectedCount.textContent = count > 0 ? `${count} ${gettext("selected")}` : ""
        selectedCount.hidden = count === 0
    }
    if (selectAll && checkboxes.length > 0) {
        selectAll.checked = count > 0 && count === checkboxes.length
        selectAll.indeterminate = count > 0 && count < checkboxes.length
    }
}

if (selectAll && checkboxes.length > 0) {
    selectAll.addEventListener("change", () => {
        checkboxes.forEach((cb) => {
            cb.checked = selectAll.checked
        })
        refreshSelectionUi()
    })
    checkboxes.forEach((cb) => {
        cb.addEventListener("change", refreshSelectionUi)
    })
    refreshSelectionUi()
}

const classifySelected = (selected) => {
    const groups = {
        send: [],
        resend: [],
        claimed: 0,
        skipped: 0,
    }
    selected.forEach((cb) => {
        const name = truncateName(cb.dataset.speakerName || "")
        const state = cb.dataset.voucherState || "dash"
        if (state === "not_sent") groups.send.push(name)
        else if (state === "sent") groups.resend.push(name)
        else if (state === "claimed") groups.claimed += 1
        else groups.skipped += 1
    })
    return groups
}

const renderChips = (names) => {
    const wrap = document.createElement("div")
    wrap.className = "speaker-voucher-bulk-chips"
    names.forEach((name) => {
        const chip = document.createElement("span")
        chip.className = "speaker-voucher-bulk-chip"
        chip.textContent = name
        chip.title = name
        wrap.appendChild(chip)
    })
    return wrap
}

const renderActionGroup = (label, names, modifier) => {
    if (!names.length) return null
    const section = document.createElement("section")
    section.className = `speaker-voucher-bulk-group speaker-voucher-bulk-group--${modifier}`

    const heading = document.createElement("div")
    heading.className = "speaker-voucher-bulk-group-head"
    const badge = document.createElement("span")
    badge.className = `speaker-voucher-badge speaker-voucher-badge--${modifier === "send" ? "default" : "sent"}`
    badge.textContent = withCount(label, names.length)
    heading.appendChild(badge)
    section.appendChild(heading)
    section.appendChild(renderChips(names))
    return section
}

const fillBulkDialog = (groups) => {
    if (!bulkGroups) return 0
    bulkGroups.replaceChildren()

    const sendLabel = ngettext("Send (%(count)s)", "Send (%(count)s)", groups.send.length)
    const resendLabel = ngettext("Resend (%(count)s)", "Resend (%(count)s)", groups.resend.length)

    ;[
        renderActionGroup(sendLabel, groups.send, "send"),
        renderActionGroup(resendLabel, groups.resend, "resend"),
    ]
        .filter(Boolean)
        .forEach((section) => bulkGroups.appendChild(section))

    const actionable = groups.send.length + groups.resend.length
    if (bulkSummary) {
        if (actionable > 0) {
            bulkSummary.textContent = withCount(
                ngettext(
                    "Email %(count)s selected speaker.",
                    "Email %(count)s selected speakers.",
                    actionable,
                ),
                actionable,
            )
            bulkSummary.classList.remove("d-none")
        } else {
            bulkSummary.textContent = ""
            bulkSummary.classList.add("d-none")
        }
    }

    if (bulkSkipped) {
        const parts = []
        if (groups.claimed) {
            parts.push(
                withCount(
                    ngettext("%(count)s already claimed", "%(count)s already claimed", groups.claimed),
                    groups.claimed,
                ),
            )
        }
        if (groups.skipped) {
            parts.push(
                withCount(
                    ngettext("%(count)s not eligible", "%(count)s not eligible", groups.skipped),
                    groups.skipped,
                ),
            )
        }
        if (parts.length) {
            bulkSkipped.textContent = `${gettext("Skipped")}: ${parts.join(" · ")}`
            bulkSkipped.classList.remove("d-none")
        } else {
            bulkSkipped.textContent = ""
            bulkSkipped.classList.add("d-none")
        }
    }

    if (bulkConfirmLabel) {
        if (groups.send.length && !groups.resend.length) {
            bulkConfirmLabel.textContent = gettext("Send vouchers")
        } else if (!groups.send.length && groups.resend.length) {
            bulkConfirmLabel.textContent = gettext("Resend vouchers")
        } else {
            bulkConfirmLabel.textContent = gettext("Send vouchers")
        }
    }

    return actionable
}

const submitBulkForm = (selected) => {
    if (!bulkForm) return
    bulkForm.querySelectorAll('input[name="profile_ids"]').forEach((el) => el.remove())
    selected.forEach((cb) => {
        const hidden = document.createElement("input")
        hidden.type = "hidden"
        hidden.name = "profile_ids"
        hidden.value = cb.dataset.profileId
        bulkForm.appendChild(hidden)
    })
    if (bulkSendBtn) bulkSendBtn.disabled = true
    if (bulkConfirmBtn) bulkConfirmBtn.disabled = true
    bulkForm.requestSubmit()
}

bulkSendBtn?.addEventListener("click", () => {
    if (!bulkForm) return
    const selected = selectedCheckboxes()
    if (selected.length === 0) {
        window.alert(gettext("Select at least one speaker."))
        return
    }

    if (!bulkDialog || !bulkGroups) {
        submitBulkForm(selected)
        return
    }

    const groups = classifySelected(selected)
    const actionable = fillBulkDialog(groups)
    const hasActionable = actionable > 0

    if (bulkEmpty) bulkEmpty.classList.toggle("d-none", hasActionable)
    if (bulkPreview) {
        bulkPreview.classList.toggle("d-none", !hasActionable)
        bulkPreview.open = false
    }
    if (bulkConfirmBtn) {
        bulkConfirmBtn.disabled = !hasActionable
        bulkConfirmBtn.classList.toggle("d-none", !hasActionable)
    }
    bulkDialog.showModal()
})

document.getElementById("speaker-voucher-bulk-cancel")?.addEventListener("click", () => {
    bulkDialog?.close()
})

bulkConfirmBtn?.addEventListener("click", () => {
    const selected = selectedCheckboxes().filter((cb) => {
        const state = cb.dataset.voucherState || "dash"
        return state === "not_sent" || state === "sent"
    })
    if (selected.length === 0) return
    bulkDialog?.close()
    submitBulkForm(selected)
})

window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
        if (bulkSendBtn) bulkSendBtn.disabled = false
        if (bulkConfirmBtn) bulkConfirmBtn.disabled = false
        refreshSelectionUi()
    }
})

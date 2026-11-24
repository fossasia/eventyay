/* Speakers list: bulk voucher selection and confirm dialog. */

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

const bulkSendBtn = document.getElementById("speaker-bulk-send-btn")
const bulkForm = document.getElementById("speaker-bulk-voucher-form")
const bulkDialog = document.getElementById("speaker-voucher-bulk-confirm")
const bulkSkipped = document.getElementById("speaker-voucher-bulk-skipped")
const bulkEmpty = document.getElementById("speaker-voucher-bulk-empty")
const bulkConfirmBtn = document.getElementById("speaker-voucher-bulk-confirm-btn")
const bulkConfirmLabel = document.getElementById("speaker-voucher-bulk-confirm-label")
const bulkSummaryList = document.getElementById("speaker-voucher-bulk-summary-list")
const sendCountEl = document.getElementById("speaker-voucher-bulk-send-count")
const resendCountEl = document.getElementById("speaker-voucher-bulk-resend-count")
const sendLabelEl = document.getElementById("speaker-voucher-bulk-send-label")
const resendLabelEl = document.getElementById("speaker-voucher-bulk-resend-label")
const usedCountEl = document.getElementById("speaker-voucher-bulk-used-count")
const remainingCountEl = document.getElementById("speaker-voucher-bulk-remaining-count")
const selectedCount = document.getElementById("speakers-selected-count")

const currentCheckboxes = () => document.querySelectorAll(".speaker-checkbox")
const currentSelectAll = () => document.getElementById("select-all-speakers")
const selectedCheckboxes = () => Array.from(currentCheckboxes()).filter((cb) => cb.checked)

const refreshSelectionUi = () => {
    const checkboxes = currentCheckboxes()
    const selectAll = currentSelectAll()
    const count = selectedCheckboxes().length
    if (selectedCount) {
        selectedCount.textContent = count > 0 ? `${count} ${gettext("selected")}` : ""
        selectedCount.hidden = count === 0
    }
    if (selectAll && checkboxes.length > 0) {
        selectAll.checked = count > 0 && count === checkboxes.length
        selectAll.indeterminate = count > 0 && count < checkboxes.length
    } else if (selectAll) {
        selectAll.checked = false
        selectAll.indeterminate = false
    }
}

// Delegated handlers survive AJAX result replacement of the speakers table.
document.addEventListener("change", (event) => {
    const target = event.target
    if (!(target instanceof HTMLInputElement)) {
        return
    }
    if (target.id === "select-all-speakers") {
        currentCheckboxes().forEach((cb) => {
            cb.checked = target.checked
        })
        refreshSelectionUi()
        return
    }
    if (target.classList.contains("speaker-checkbox")) {
        refreshSelectionUi()
    }
})

refreshSelectionUi()

document.addEventListener("eventyay:ajax-results-replaced", () => {
    refreshSelectionUi()
})

const classifySelected = (selected) => {
    const groups = { send: 0, resend: 0, claimed: 0, skipped: 0, needsCode: 0 }
    selected.forEach((cb) => {
        const state = cb.dataset.voucherState || "dash"
        if (state === "not_sent") {
            groups.send += 1
            if (cb.dataset.voucherNeedsCode === "1") {
                groups.needsCode += 1
            }
        } else if (state === "sent") {
            groups.resend += 1
        } else if (state === "claimed") {
            groups.claimed += 1
        } else {
            groups.skipped += 1
        }
    })
    return groups
}

const setRowVisible = (labelEl, valueEl, visible) => {
    if (labelEl) labelEl.classList.toggle("d-none", !visible)
    if (valueEl) valueEl.classList.toggle("d-none", !visible)
}

const fillBulkDialog = (groups) => {
    const remaining = Number.parseInt(bulkDialog?.dataset.vouchersRemaining || "0", 10) || 0
    // Only new allocations consume a batch code; retries of a failed send reuse theirs.
    const vouchersUsed = groups.needsCode
    const remainingAfter = Math.max(remaining - vouchersUsed, 0)

    if (sendCountEl) sendCountEl.textContent = String(groups.send)
    if (resendCountEl) resendCountEl.textContent = String(groups.resend)
    if (usedCountEl) usedCountEl.textContent = String(vouchersUsed)
    if (remainingCountEl) remainingCountEl.textContent = String(remainingAfter)

    setRowVisible(sendLabelEl, sendCountEl, groups.send > 0)
    setRowVisible(resendLabelEl, resendCountEl, groups.resend > 0)

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
        bulkConfirmLabel.textContent =
            !groups.send && groups.resend ? gettext("Resend vouchers") : gettext("Send vouchers")
    }

    return groups.send + groups.resend
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

    if (!bulkDialog) {
        submitBulkForm(selected)
        return
    }

    const groups = classifySelected(selected)
    const actionable = fillBulkDialog(groups)
    const hasActionable = actionable > 0

    if (bulkSummaryList) bulkSummaryList.classList.toggle("d-none", !hasActionable)
    if (bulkEmpty) bulkEmpty.classList.toggle("d-none", hasActionable)
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

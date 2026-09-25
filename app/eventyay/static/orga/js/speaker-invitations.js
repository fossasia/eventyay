const SECTION_SELECTOR = "[data-speakers-section]"
const FORM_SELECTOR = "[data-add-speaker-form]"
const SUBMIT_SELECTOR = "[data-add-speaker-submit]"
const RESEND_SELECTOR = "[data-resend-invitation]"
const REVOKE_SELECTOR = "[data-revoke-invitation]"

const getCsrfToken = () => {
    const field = document.querySelector("[name=csrfmiddlewaretoken]")
    return field ? field.value : ""
}

const clearFeedback = (section) => {
    const alert = section.querySelector(".speaker-invitation-feedback")
    if (alert) alert.remove()
}

const showFeedback = (section, message, isError) => {
    let alert = section.querySelector(".speaker-invitation-feedback")
    if (!alert) {
        alert = document.createElement("div")
        alert.className = "speaker-invitation-feedback alert"
        section.prepend(alert)
    }
    alert.classList.toggle("alert-danger", !!isError)
    alert.classList.toggle("alert-success", !isError)
    alert.textContent = message
}

const showFieldErrors = (form, errors) => {
    form.querySelectorAll(".invalid-feedback.speaker-invitation-error").forEach((node) => node.remove())
    form.querySelectorAll(".is-invalid").forEach((node) => node.classList.remove("is-invalid"))

    const unattached = []
    Object.entries(errors || {}).forEach(([field, messages]) => {
        const input = form.querySelector(`[name="${field}"]`)
        const text = messages.map((entry) => entry.message).join(" ")
        if (!input) {
            unattached.push(text)
            return
        }
        input.classList.add("is-invalid")
        const hint = document.createElement("div")
        hint.className = "invalid-feedback speaker-invitation-error d-block"
        hint.textContent = text
        input.parentNode.appendChild(hint)
    })
    return unattached
}

const bindSection = (section) => {
    const form = section.querySelector(FORM_SELECTOR)
    if (form) {
        form.addEventListener("submit", (event) => {
            event.preventDefault()
            submitForm(section, form)
        })
    }
    section.querySelectorAll(RESEND_SELECTOR).forEach((button) => {
        button.addEventListener("click", () => resendInvitation(section, button))
    })
    section.querySelectorAll(REVOKE_SELECTOR).forEach((button) => {
        button.addEventListener("click", () => revokeInvitation(section, button))
    })
}

const replaceSection = (section, html) => {
    const parsed = new DOMParser().parseFromString(html, "text/html")
    section.replaceChildren(...parsed.body.childNodes)
    bindSection(section)
    document.dispatchEvent(new CustomEvent("eventyay:speakers-updated"))
}

const startSending = (button) => {
    if (!button) return null
    const label = [...button.childNodes]
    button.disabled = true
    button.replaceChildren(document.createTextNode(button.dataset.sendingText || ""))
    return label
}

const stopSending = (button, label) => {
    if (!button || !label || !button.isConnected) return
    button.disabled = false
    button.replaceChildren(...label)
}

const submitForm = async (section, form) => {
    const button = form.querySelector(SUBMIT_SELECTOR)
    const originalLabel = startSending(button)

    try {
        const response = await fetch(window.location.href, {
            method: "POST",
            headers: { "X-Requested-With": "XMLHttpRequest" },
            body: new FormData(form),
        })
        const data = await response.json().catch(() => ({}))

        if (response.status === 400 && data.errors) {
            clearFeedback(section)
            const unattached = showFieldErrors(form, data.errors)
            if (unattached.length) {
                showFeedback(section, unattached.join(" "), true)
            }
            return
        }
        if (!response.ok) {
            showFeedback(section, data.message || form.dataset.errorText, true)
            return
        }
        replaceSection(section, data.html)
        showFeedback(section, data.message, !data.success)
    } catch (error) {
        showFeedback(section, form.dataset.errorText, true)
    } finally {
        stopSending(button, originalLabel)
    }
}

const resendInvitation = async (section, button) => {
    const originalLabel = startSending(button)

    const body = new FormData()
    body.append("csrfmiddlewaretoken", getCsrfToken())

    try {
        const response = await fetch(button.dataset.resendInvitation, {
            method: "POST",
            headers: { "X-Requested-With": "XMLHttpRequest" },
            body,
        })
        const data = await response.json().catch(() => ({}))
        if (data.html) {
            replaceSection(section, data.html)
        }
        showFeedback(section, data.message || button.dataset.errorText, !data.success)
    } catch (error) {
        showFeedback(section, button.dataset.errorText, true)
    } finally {
        stopSending(button, originalLabel)
    }
}

const revokeInvitation = async (section, button) => {
    if (button.dataset.confirmText && !window.confirm(button.dataset.confirmText)) return
    button.disabled = true

    const body = new FormData()
    body.append("csrfmiddlewaretoken", getCsrfToken())

    try {
        const response = await fetch(button.dataset.revokeInvitation, {
            method: "POST",
            headers: { "X-Requested-With": "XMLHttpRequest" },
            body,
        })
        const data = await response.json().catch(() => ({}))
        if (data.html) {
            replaceSection(section, data.html)
        }
        showFeedback(section, data.message || button.dataset.errorText, !data.success)
    } catch (error) {
        showFeedback(section, button.dataset.errorText, true)
    } finally {
        if (button.isConnected) button.disabled = false
    }
}

const section = document.querySelector(SECTION_SELECTOR)
if (section) {
    bindSection(section)
}

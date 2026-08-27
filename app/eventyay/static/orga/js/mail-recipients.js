/* Keeps the audience summary in step with the recipient filters, and fills the
 * recipient list dialog from the same endpoint the send path filters on. */

const MESSAGE_FIELDS = /^(csrfmiddlewaretoken|action|subject_|text_|reply_to|bcc|scheduled_at|delivery_mode|skip_queue|test_email)/

// Filters the composer was opened with live in the page URL rather than in the
// form, so they have to be carried over separately.
const URL_FILTER_KEYS = ["q", "question", "answer", "answer__options", "unanswered"]

const buildFilterQuery = (form) => {
    const params = new URLSearchParams()
    new FormData(form).forEach((value, key) => {
        if (!MESSAGE_FIELDS.test(key) && value !== "") {
            params.append(key, value)
        }
    })
    const pageParams = new URLSearchParams(window.location.search)
    URL_FILTER_KEYS.forEach((key) => {
        const value = pageParams.get(key)
        if (value && !params.has(key)) {
            params.append(key, value)
        }
    })
    return params
}

/**
 * @throws {Error} when the recipient endpoint is unreachable or refuses the request
 */
const fetchRecipients = async (url, form) => {
    const response = await fetch(`${url}?${buildFilterQuery(form)}`, {
        headers: { Accept: "application/json" },
    })
    if (!response.ok) {
        throw new Error(`Recipient lookup failed with status ${response.status}`)
    }
    return response.json()
}

const renderCount = (badge, count) => {
    const label = count === 1 ? badge.dataset.labelOne : badge.dataset.labelOther
    badge.textContent = `${count} ${label}`
    badge.hidden = false
}

const clearFilters = (form) => {
    const filters = form.querySelector(".composer-filters")
    if (!filters) return
    // Choices keeps its own state and ignores the underlying select, so drop the
    // selections through the remove buttons it renders. It acts on mousedown,
    // which click() does not fire.
    const nextButton = () => filters.querySelector(".choices__list--multiple .choices__button")
    let button = nextButton()
    let guard = 0
    while (button && guard < 500) {
        button.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }))
        button = nextButton()
        guard += 1
    }
}

const renderRecipients = (body, recipients) => {
    body.replaceChildren()
    if (!recipients.length) {
        const empty = document.createElement("p")
        empty.className = "text-muted"
        empty.textContent = body.dataset.emptyLabel
        body.appendChild(empty)
        return
    }
    const list = document.createElement("ul")
    list.className = "list-group list-group-flush"
    recipients.forEach((recipient) => {
        const item = document.createElement("li")
        item.className = "list-group-item"
        const name = document.createElement("strong")
        name.textContent = recipient.name
        const email = document.createElement("span")
        email.className = "text-muted ml-2"
        email.textContent = recipient.email
        item.append(name, email)
        recipient.submissions.forEach((submission) => {
            const line = document.createElement("div")
            line.className = "text-muted"
            line.textContent = `${submission.title} (${submission.state})`
            item.appendChild(line)
        })
        if (recipient.directly_selected) {
            const line = document.createElement("div")
            line.className = "text-muted"
            line.textContent = body.dataset.directLabel
            item.appendChild(line)
        }
        list.appendChild(item)
    })
    body.appendChild(list)
}

const initRecipientPreview = () => {
    const trigger = document.querySelector("#show-recipient-list")
    const badge = document.querySelector("#recipient-count")
    const body = document.querySelector("#recipient-list-body")
    if (!trigger || !badge || !body) return

    const form = trigger.closest("form")
    const url = trigger.dataset.recipientsUrl

    const summary = document.querySelector("#recipient-summary")

    const refreshCount = async () => {
        try {
            const data = await fetchRecipients(url, form)
            renderCount(badge, data.count)
            if (summary) renderCount(summary, data.count)
        } catch (error) {
            console.error("Could not refresh the recipient count", error)
            badge.hidden = true
        }
    }

    const clearButton = document.querySelector("#clear-filters")
    if (clearButton) {
        clearButton.addEventListener("click", () => clearFilters(form))
    }

    let timer = null
    form.addEventListener("change", (e) => {
        if (MESSAGE_FIELDS.test(e.target.name || "")) return
        window.clearTimeout(timer)
        timer = window.setTimeout(refreshCount, 300)
    })

    trigger.addEventListener("click", async () => {
        body.textContent = body.dataset.loadingLabel
        try {
            const data = await fetchRecipients(url, form)
            renderCount(badge, data.count)
            renderRecipients(body, data.recipients)
        } catch (error) {
            console.error("Could not load the recipient list", error)
            body.textContent = body.dataset.errorLabel
        }
    })

    document.querySelectorAll("[data-recipient-close]").forEach((button) => {
        button.addEventListener("click", () => {
            document.querySelector("#recipient-list-dialog").close()
        })
    })

    refreshCount()
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initRecipientPreview)
} else {
    initRecipientPreview()
}

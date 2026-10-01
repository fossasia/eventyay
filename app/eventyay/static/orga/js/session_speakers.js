const SECTION_SELECTOR = "[data-session-speakers]"
const FORM_SELECTOR = "[data-session-speaker-form]"

const sendForm = async (form) => {
    const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin",
        redirect: "manual",
    })
    return response.type === "opaqueredirect"
}

const bindForm = (form) => {
    form.addEventListener("submit", async (event) => {
        event.preventDefault()
        const button = form.querySelector("[type=submit]")
        if (button) button.disabled = true
        try {
            if (await sendForm(form)) {
                window.location.assign(window.location.pathname + window.location.search)
                return
            }
        } catch (error) {
            console.error("Could not update the session speakers", error)
        }
        HTMLFormElement.prototype.submit.call(form)
    })
}

document.querySelectorAll(`${SECTION_SELECTOR} ${FORM_SELECTOR}`).forEach(bindForm)

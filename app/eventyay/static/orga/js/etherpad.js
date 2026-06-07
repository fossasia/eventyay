// Confirmation guard for Etherpad pad (re)generation. Any form carrying a
// data-confirm attribute asks the user before submitting, so that an existing
// Etherpad link is never replaced without explicit confirmation.
document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
        const message = form.getAttribute("data-confirm")
        if (message && !window.confirm(message)) {
            event.preventDefault()
        }
    })
})

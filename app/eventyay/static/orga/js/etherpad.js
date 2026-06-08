// Confirmation guard for Etherpad pad (re)generation. Any element carrying a
// data-confirm attribute asks the user before its action proceeds, so that an
// existing Etherpad link is never replaced without explicit confirmation.
document.querySelectorAll("[data-confirm]").forEach((el) => {
    el.addEventListener("click", (event) => {
        const message = el.getAttribute("data-confirm")
        if (message && !window.confirm(message)) {
            event.preventDefault()
        }
    })
})

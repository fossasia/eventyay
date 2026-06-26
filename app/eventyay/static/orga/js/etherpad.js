const getCsrfToken = () => {
    const field = document.querySelector("[name=csrfmiddlewaretoken]")
    return field ? field.value : ""
}

const generatePad = async (button) => {
    const confirmMessage = button.getAttribute("data-confirm")
    if (confirmMessage && !window.confirm(confirmMessage)) {
        return
    }

    const body = new FormData()
    body.append("csrfmiddlewaretoken", getCsrfToken())
    if (button.dataset.force === "true") {
        body.append("force", "true")
    }

    button.disabled = true
    try {
        const response = await fetch(button.dataset.url, {
            method: "POST",
            headers: { "X-Requested-With": "XMLHttpRequest" },
            body,
        })
        const data = await response.json().catch(() => ({}))
        if (!response.ok) {
            window.alert(data.error || button.dataset.errorText)
            return
        }
        const input = document.querySelector("#id_etherpad_url")
        if (input) {
            input.value = data.url
        }
        button.dataset.force = "true"
        if (button.dataset.replaceConfirm) {
            button.setAttribute("data-confirm", button.dataset.replaceConfirm)
        }
    } catch (error) {
        window.alert(button.dataset.errorText)
    } finally {
        button.disabled = false
    }
}

document.querySelectorAll("[data-etherpad-generate]").forEach((button) => {
    button.addEventListener("click", () => generatePad(button))
})

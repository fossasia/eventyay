const handleFeaturedChange = (element) => {
    const statusWrapper = element.closest("td")
    if (!statusWrapper) {
        return
    }
    const resetStatus = () => {
        statusWrapper.querySelectorAll("i.working, i.done, i.fail").forEach((icon) => {
            icon.classList.add("d-none")
        })
    }
    const setStatus = (statusName) => {
        const statusIcon = statusWrapper.querySelector("." + statusName)
        if (!statusIcon) {
            return
        }
        resetStatus()
        statusIcon.classList.remove("d-none")
        setTimeout(resetStatus, 3000)
    }
    const fail = () => {
        element.checked = !element.checked
        setStatus("fail")
    }

    setStatus("working")

    const url = element.dataset.url
    if (!url) {
        fail()
        return
    }
    const options = {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("eventyay_csrftoken"),
        },
        credentials: "include",
    }

    fetch(url, options)
        .then((response) => {
            if (response.status === 200) {
                setStatus("done")
            } else {
                fail()
            }
        })
        .catch((error) => fail())
}

const initScrollPosition = () => {
    document.querySelectorAll(".keep-scroll-position").forEach((el) => {
        el.addEventListener("click", () => {
            sessionStorage.setItem("scroll-position", window.scrollY)
        })
    })
    const oldScrollY = sessionStorage.getItem("scroll-position")
    if (oldScrollY) {
        window.scroll(window.scrollX, Math.max(oldScrollY, window.innerHeight))
        sessionStorage.removeItem("scroll-position")
    }
}

const getCookie = (name) => {
    let cookieValue = null
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";")
        for (var i = 0; i < cookies.length; i++) {
            let cookie = cookies[i].trim()
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === name + "=") {
                cookieValue = decodeURIComponent(
                    cookie.substring(name.length + 1),
                )
                break
            }
        }
    }
    return cookieValue
}

const updateArrivalButton = (button, hasArrived) => {
    const arrivedLabel = button.dataset.labelArrived
    const notArrivedLabel = button.dataset.labelNotArrived
    if (hasArrived) {
        button.classList.remove("btn-speaker-arrived")
        button.classList.add("btn-speaker-not-arrived")
        button.textContent = notArrivedLabel
    } else {
        button.classList.remove("btn-speaker-not-arrived")
        button.classList.add("btn-speaker-arrived")
        button.textContent = arrivedLabel
    }
}

const handleArrivalSubmit = (form) => {
    form.addEventListener("submit", (event) => {
        event.preventDefault()
        const button = form.querySelector('button[type="submit"]')
        if (!button) {
            return
        }
        button.disabled = true
        fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            credentials: "include",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
        })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Speaker arrival toggle failed")
                }
                return response.json()
            })
            .then((data) => {
                updateArrivalButton(button, data.has_arrived)
            })
            .catch(() => {})
            .finally(() => {
                button.disabled = false
            })
    })
}

const initArrivalToggles = (root = document) => {
    root.querySelectorAll("form.speaker-arrival-form").forEach((form) => {
        if (form.dataset.arrivalInitialized) {
            return
        }
        form.dataset.arrivalInitialized = "true"
        handleArrivalSubmit(form)
    })
}

const initFeaturedToggles = (root = document) => {
    root
        .querySelectorAll("input.submission_featured")
        .forEach((element) =>
            element.addEventListener("change", () =>
                handleFeaturedChange(element),
            ),
        )
}

onReady(() => {
    initScrollPosition()
    initFeaturedToggles()
    initArrivalToggles()
})

// Re-bind toggles inside table regions.
document.addEventListener("eventyay:ajax-results-replaced", (event) => {
    const container = event.detail?.container ?? document
    initFeaturedToggles(container)
    initArrivalToggles(container)
})

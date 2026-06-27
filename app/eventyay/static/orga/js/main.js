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

        if (statusWrapper.resetTimeout) {
            clearTimeout(statusWrapper.resetTimeout)
        }
        statusWrapper.resetTimeout = setTimeout(resetStatus, 3000)
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
})

// Re-bind featured toggles inside table regions replaced by AJAX filters.
document.addEventListener("eventyay:ajax-results-replaced", (event) => {
    initFeaturedToggles(event.detail?.container ?? document)
})

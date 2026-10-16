/* This file will be loaded on all pretalx pages.
 * It will be loaded before all other scripts. */

/* This function makes sure a given function is run after the DOM is fully loaded. */
const onReady = (fn) => {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", fn)
    } else {
        fn()
    }
}

onReady(() => {
    document.querySelectorAll("[data-embed-formats]").forEach((root) => {
        const choices = root.querySelectorAll("[data-embed-choice]")
        const panels = root.querySelectorAll("[data-embed-panel]")

        function show(format) {
            panels.forEach((panel) => {
                panel.hidden = panel.dataset.embedPanel !== format
            })
            choices.forEach((choice) => {
                const selected = choice.dataset.embedChoice === format
                choice.classList.toggle("active", selected)
                choice.setAttribute("aria-pressed", selected ? "true" : "false")
            })
        }

        choices.forEach((choice) => {
            choice.addEventListener("click", () => {
                show(choice.dataset.embedChoice)
            })
        })
        show("html")
    })
})

{
    const logoutVersionKey = "eventyay.logout-version"
    let pageLogoutVersion = null

    try {
        pageLogoutVersion = sessionStorage.getItem(logoutVersionKey) || "0"
    } catch (error) {
        console.warn("Unable to read the logout version from session storage", error)
    }

    function isLogoutUrl(value) {
        const url = new URL(value, window.location.href)
        if (url.origin !== window.location.origin) return false

        let path
        try {
            path = decodeURIComponent(url.pathname)
        } catch (error) {
            console.warn("Unable to decode a navigation path", error)
            return false
        }

        const commonLogout = /(?:^|\/)common\/logout\/?$/.test(path)
        const eventLogout = /(?:^|\/)[^/]+\/[^/]+\/logout\/?$/.test(path)
        return commonLogout || eventLogout
    }

    function markLogoutNavigation() {
        if (pageLogoutVersion === null) return

        try {
            const currentVersion = Number(sessionStorage.getItem(logoutVersionKey)) || 0
            sessionStorage.setItem(logoutVersionKey, String(currentVersion + 1))
        } catch (error) {
            console.warn("Unable to update the logout version in session storage", error)
        }
    }

    document.addEventListener("submit", (event) => {
        if (event.target instanceof HTMLFormElement && isLogoutUrl(event.target.action)) {
            markLogoutNavigation()
        }
    }, true)

    document.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) return

        const link = event.target.closest("a[href]")
        if (link && isLogoutUrl(link.href)) markLogoutNavigation()
    }, true)

    window.addEventListener("pageshow", (event) => {
        if (!event.persisted || pageLogoutVersion === null) return

        try {
            if ((sessionStorage.getItem(logoutVersionKey) || "0") !== pageLogoutVersion) {
                window.location.replace(window.location.href)
            }
        } catch (error) {
            console.warn("Unable to check the logout version after page restore", error)
        }
    })
}

/*
 * Fullscreen mode for the organiser schedule editor.
 *
 * Expands the schedule editing area to the whole browser viewport, hiding the
 * global navigation, the organiser sidebar and the "New release"/"Actions"
 * controls so organisers can focus on building the schedule. The native
 * Fullscreen API is used where available (so Esc exits), with a CSS-only
 * fallback (the `schedule-fullscreen` body class) for browsers without it.
 */
onReady(() => {
    const toggle = document.getElementById("schedule-fullscreen-toggle")
    const target = document.getElementById("page-content")
    if (!toggle || !target) return

    const cls = "schedule-fullscreen"
    const labelEl = toggle.querySelector(".fullscreen-label")
    const iconEl = toggle.querySelector("i.fa")
    const enterLabel = toggle.dataset.labelEnter || "Fullscreen"
    const exitLabel = toggle.dataset.labelExit || "Exit fullscreen"

    const requestFullscreen = target.requestFullscreen || target.webkitRequestFullscreen
    const exitFullscreen = document.exitFullscreen || document.webkitExitFullscreen
    const fullscreenElement = () => document.fullscreenElement || document.webkitFullscreenElement
    const nativeSupported = Boolean(requestFullscreen && exitFullscreen)

    const setState = (active) => {
        document.body.classList.toggle(cls, active)
        toggle.setAttribute("aria-pressed", active ? "true" : "false")
        if (labelEl) labelEl.textContent = active ? exitLabel : enterLabel
        if (iconEl) {
            iconEl.classList.toggle("fa-expand", !active)
            iconEl.classList.toggle("fa-compress", active)
        }
    }

    const enter = () => {
        if (nativeSupported) {
            Promise.resolve(requestFullscreen.call(target)).catch(() => setState(true))
        } else {
            setState(true)
        }
    }

    const exit = () => {
        if (nativeSupported && fullscreenElement()) {
            Promise.resolve(exitFullscreen.call(document)).catch(() => setState(false))
        } else {
            setState(false)
        }
    }

    toggle.addEventListener("click", () => {
        document.body.classList.contains(cls) ? exit() : enter()
    })

    if (nativeSupported) {
        const onChange = () => setState(Boolean(fullscreenElement()))
        document.addEventListener("fullscreenchange", onChange)
        document.addEventListener("webkitfullscreenchange", onChange)
    } else {
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && document.body.classList.contains(cls)) exit()
        })
    }
})

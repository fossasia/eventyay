document
    .querySelectorAll(".cfp-option-table .require input")
    .forEach((element) => {
        element.addEventListener("click", (ev) => {
            if (ev.target.checked) {
                ev.target.parentElement.parentElement.parentElement.parentElement.querySelector(
                    ".request input",
                ).checked = true
            }
        })
    })

document.addEventListener("DOMContentLoaded", () => {
    const settingsButton = document.querySelector(".profile-picture-settings-button")
    const settingsPopover = document.querySelector(".profile-picture-settings-popover")
    if (!settingsButton || !settingsPopover) return

    const closePopover = () => {
        settingsPopover.classList.add("d-none")
        settingsButton.setAttribute("aria-expanded", "false")
    }

    const openPopover = () => {
        settingsPopover.classList.remove("d-none")
        settingsPopover.style.visibility = "hidden"

        const buttonRect = settingsButton.getBoundingClientRect()
        const popoverRect = settingsPopover.getBoundingClientRect()
        const margin = 8
        const left = Math.min(
            Math.max(margin, buttonRect.right - popoverRect.width),
            window.innerWidth - popoverRect.width - margin,
        )
        const spaceAbove = buttonRect.top - popoverRect.height - margin
        const opensAbove = spaceAbove >= margin
        const top = opensAbove ? spaceAbove : buttonRect.bottom + margin

        settingsPopover.style.left = `${left}px`
        settingsPopover.style.top = `${top}px`
        settingsPopover.dataset.placement = opensAbove ? "above" : "below"
        settingsPopover.style.visibility = ""
        settingsButton.setAttribute("aria-expanded", "true")
    }

    settingsButton.addEventListener("click", (event) => {
        event.stopPropagation()
        if (settingsPopover.classList.contains("d-none")) {
            openPopover()
        } else {
            closePopover()
        }
    })

    settingsPopover.addEventListener("click", (event) => event.stopPropagation())
    document.addEventListener("click", closePopover)
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !settingsPopover.classList.contains("d-none")) {
            closePopover()
            settingsButton.focus()
        }
    })
    window.addEventListener("resize", closePopover)
    window.addEventListener("scroll", closePopover, true)
})

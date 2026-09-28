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

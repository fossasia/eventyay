/* Minimal enhancement to native modals, by making them close when the user clicks outside the dialog. */

;(function () {
    if (window.__eventyayModalDialogLoaded) {
        return
    }
    window.__eventyayModalDialogLoaded = true

    const setupModals = () => {
        document.querySelectorAll("[data-dialog-target]:not([data-dialog-trigger-initialized])").forEach((element) => {
            const outerDialogElement = document.querySelector(
                element.dataset.dialogTarget,
            )
            if (!outerDialogElement) return
            element.setAttribute("data-dialog-trigger-initialized", "")
            const openDialog = (ev) => {
                ev.preventDefault()
                if (typeof outerDialogElement.showModal === "function") {
                    outerDialogElement.showModal()
                }
            }
            element.addEventListener("click", openDialog)
            if (element.tagName !== "BUTTON") {
                element.addEventListener("keydown", (ev) => {
                    if (ev.key === "Enter" || ev.key === " ") {
                        if (ev.key === " ") {
                            ev.preventDefault()
                        }
                        openDialog(ev)
                    }
                })
            }
            if (outerDialogElement.hasAttribute("data-dialog-backdrop-initialized")) {
                return
            }
            outerDialogElement.setAttribute("data-dialog-backdrop-initialized", "")
            outerDialogElement.addEventListener("click", (ev) => {
                if (
                    ev.target === outerDialogElement &&
                    typeof outerDialogElement.close === "function"
                ) {
                    outerDialogElement.close()
                }
            })
        })
    }

    window.setupModals = setupModals
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupModals)
    } else {
        setupModals()
    }
})()

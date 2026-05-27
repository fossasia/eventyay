/* Minimal enhancement to native modals, by making them close when the user clicks outside the dialog. */

;(function () {
    if (window.__eventyayModalDialogLoaded) {
        return
    }
    window.__eventyayModalDialogLoaded = true

    const setupModals = () => {
        document.querySelectorAll("[data-dialog-target]:not([data-dialog-initialized])").forEach((element) => {
            const outerDialogElement = document.querySelector(
                element.dataset.dialogTarget,
            )
            if (!outerDialogElement) return
            element.setAttribute("data-dialog-initialized", "")
            element.addEventListener("click", function (ev) {
                ev.preventDefault()
                if (typeof outerDialogElement.showModal === "function") {
                    outerDialogElement.showModal()
                }
            })
            if (outerDialogElement.hasAttribute("data-dialog-initialized")) {
                return
            }
            outerDialogElement.setAttribute("data-dialog-initialized", "")
            outerDialogElement.addEventListener("click", (ev) => {
                if (ev.target === outerDialogElement) {
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

/* Minimal enhancement to native modals, by making them close when the user clicks outside the dialog. */

const setupModals = () => {
    document.querySelectorAll("[data-dialog-target]:not([data-dialog-initialized])").forEach((element) => {
        const outerDialogElement = document.querySelector(
            element.dataset.dialogTarget,
        )
        if (!outerDialogElement) return
        element.setAttribute("data-dialog-initialized", "")
        element.addEventListener("click", function (ev) {
            ev.preventDefault()
            outerDialogElement.showModal()
        })
        if (outerDialogElement.hasAttribute("data-dialog-initialized")) {
            return
        }
        outerDialogElement.setAttribute("data-dialog-initialized", "")
        outerDialogElement.addEventListener("click", () => outerDialogElement.close())
        const inner = outerDialogElement.querySelector("div, form")
        if (inner) {
            inner.addEventListener("click", (ev) => ev.stopPropagation())
        }
    })
}

onReady(setupModals)

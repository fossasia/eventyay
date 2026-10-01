// Add a lightbox to images and links with data-lightbox attribute.
// Currently loaded on every pretalx page

const setupLightbox = () => {
    const dialog = document.querySelector("dialog#lightbox-dialog")
    if (!dialog) return
    const img = dialog.querySelector("img")
    const caption = dialog.querySelector("figcaption")
    if (!img) return

    // Close the dialog when users click outside it, but do not do that when clicking
    // inside it (e.g. following a link, right-clicking etc). Then restore click-to-close
    // behaviour when clicking the close button.
    dialog.addEventListener("click", () => dialog.close())
    dialog.querySelector(".modal-card-content").addEventListener("click", (ev) => ev.stopPropagation())
    dialog.querySelector("button#lightbox-close").addEventListener("click", () => dialog.close())

    document.addEventListener("click", (ev) => {
        const element = ev.target.closest("a[data-lightbox], img[data-lightbox]")
        if (!element) return
        const image = element.tagName === "A" ? element.querySelector("img") : element
        const imageUrl = element.dataset.lightbox || element.href || image?.src
        if (!imageUrl) return
        ev.preventDefault()
        img.src = imageUrl
        caption.textContent = image?.alt || ""
        dialog.showModal()
    })
}

onReady(setupLightbox)

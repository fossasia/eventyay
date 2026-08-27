// Live client-side preview for the ImageInput widget
// (eventyay.common.forms.fields.ImageField -> common/widgets/image_input.html).
//
// The widget template always renders a `.form-image-preview` container, kept
// hidden with `d-none` until there is something to show. This script fills that
// preview with the image the user just picked -- before the form is submitted --
// mirroring the avatar preview in cfp/js/profile.js but generalised for any
// ImageInput field. The preview anchor carries `data-lightbox`, so the globally
// loaded lightbox (common/js/lightbox.js) enlarges the preview on click.

const setupImageInputs = () => {
    document.querySelectorAll("[data-image-input]").forEach((wrapper) => {
        const input = wrapper.querySelector('input[type="file"]')
        const preview = wrapper.querySelector(".form-image-preview")
        if (!input || !preview) return

        const link = preview.querySelector("a")
        const image = preview.querySelector("img")
        if (!image) return

        // The image rendered on page load (a previously saved file, if any) so
        // we can restore it when the user clears their pending selection.
        const initialSrc = image.getAttribute("src") || ""
        const clearCheckbox = wrapper.querySelector('input[type="checkbox"]')
        const removeButton = preview.querySelector(".form-image-remove")

        let currentObjectUrl = null

        const showImage = (url) => {
            image.src = url
            if (link) {
                link.href = url
            }
            preview.style.display = ""
        }

        const restore = () => {
            if (currentObjectUrl) {
                URL.revokeObjectURL(currentObjectUrl)
                currentObjectUrl = null
            }
            if (initialSrc) {
                showImage(initialSrc)
            } else {
                image.removeAttribute("src")
                if (link) link.removeAttribute("href")
                preview.style.display = "none"
            }
        }

        const clearSelection = () => {
            input.value = ""
            if (clearCheckbox) {
                clearCheckbox.checked = true
            }
            if (currentObjectUrl) {
                URL.revokeObjectURL(currentObjectUrl)
                currentObjectUrl = null
            }
            image.removeAttribute("src")
            if (link) link.removeAttribute("href")
            preview.style.display = "none"

            // Notify custom file input wrappers (e.g. fileInput.js)
            const wrapperPick = input.closest('.eventyay-file-pick-wrapper')
            const filenameEl = wrapperPick?.querySelector('.eventyay-file-name')
            if (filenameEl) {
                filenameEl.textContent = ''
            }
            input.classList.remove('file-input-has-selection')
        }

        input.addEventListener("change", (ev) => {
            const file = ev.target.files && ev.target.files[0]
            if (!file) {
                restore()
                return
            }
            if (file.type && !file.type.startsWith("image/")) {
                // A non-image was selected; don't try to render a preview for it.
                restore()
                return
            }
            // Choosing a new file supersedes a pending "clear".
            if (clearCheckbox) clearCheckbox.checked = false
            if (currentObjectUrl) {
                URL.revokeObjectURL(currentObjectUrl)
                currentObjectUrl = null
            }
            try {
                currentObjectUrl = URL.createObjectURL(file)
                showImage(currentObjectUrl)
            } catch (err) {
                const reader = new FileReader()
                reader.onload = (e) => showImage(e.target.result)
                reader.readAsDataURL(file)
            }
        })

        if (removeButton) {
            removeButton.addEventListener("click", (ev) => {
                ev.preventDefault()
                ev.stopPropagation()
                clearSelection()
            })
        }

        if (clearCheckbox) {
            clearCheckbox.addEventListener("change", (ev) => {
                if (ev.target.checked) {
                    clearSelection()
                } else {
                    restore()
                }
            })
        }
    })
}

onReady(setupImageInputs)

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

        const showImage = (url) => {
            image.src = url
            if (link) {
                link.href = url
                link.dataset.lightbox = url
            }
            preview.classList.remove("d-none")
        }

        const restore = () => {
            if (initialSrc) {
                showImage(initialSrc)
            } else {
                preview.classList.add("d-none")
            }
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
            const reader = new FileReader()
            reader.onload = (e) => showImage(e.target.result)
            reader.readAsDataURL(file)
        })

        if (clearCheckbox) {
            clearCheckbox.addEventListener("change", (ev) => {
                if (ev.target.checked) {
                    input.value = ""
                    preview.classList.add("d-none")
                } else {
                    restore()
                }
            })
        }
    })
}

onReady(setupImageInputs)

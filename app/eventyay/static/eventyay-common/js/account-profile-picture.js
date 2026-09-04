const fileInput = document.querySelector('#id_profile_picture')
const clearInput = document.querySelector('#id_clear_profile_picture')
const preview = document.querySelector('.user-avatar-preview')
const previewImage = preview?.querySelector('.user-avatar-preview-image')
const previewLink = preview?.querySelector('a')
const cropDialog = document.querySelector('#profile-picture-cropper')
const cropImage = document.querySelector('#profile-picture-cropper-image')
const applyCropButton = document.querySelector('[data-profile-picture-crop-apply]')
const cancelCropButton = document.querySelector('[data-profile-picture-crop-cancel]')

let cropper
let selectedFile
let previewObjectUrl

function showPreview(url) {
    if (!preview || !previewImage || !previewLink) return

    previewImage.src = url
    previewLink.href = url
    preview.classList.remove('d-none')
}

function hidePreview() {
    preview?.classList.add('d-none')
}

function closeCropDialog() {
    cropper?.destroy()
    cropper = null
    cropImage.removeAttribute('src')
    cropDialog.close()
}

function resetSelectedFile() {
    fileInput.value = ''
    selectedFile = null
    if (previewImage?.dataset.originalSrc) {
        showPreview(previewImage.dataset.originalSrc)
    } else {
        hidePreview()
    }
}

function createCroppedFile(canvas, file) {
    return new Promise((resolve) => {
        const type = file.type === 'image/jpeg' ? 'image/jpeg' : 'image/png'
        canvas.toBlob((blob) => {
            if (!blob) {
                resolve(null)
                return
            }

            const extension = type === 'image/jpeg' ? 'jpg' : 'png'
            resolve(new File([blob], `profile-picture.${extension}`, {type}))
        }, type, 0.9)
    })
}

async function applyCrop() {
    if (!cropper || !selectedFile) return

    const croppedFile = await createCroppedFile(cropper.getCroppedCanvas(), selectedFile)
    if (!croppedFile) {
        console.error('[account-profile-picture] Failed to create cropped image')
        return
    }

    const transfer = new DataTransfer()
    transfer.items.add(croppedFile)
    fileInput.files = transfer.files

    if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl)
    previewObjectUrl = URL.createObjectURL(croppedFile)
    showPreview(previewObjectUrl)
    if (clearInput) clearInput.checked = false
    closeCropDialog()
}

function openCropDialog(file) {
    selectedFile = file
    if (typeof window.Cropper === 'undefined') {
        console.error('[account-profile-picture] Cropper.js is unavailable')
        showPreview(URL.createObjectURL(file))
        return
    }

    const imageUrl = URL.createObjectURL(file)
    cropImage.onload = () => {
        cropper = new window.Cropper(cropImage, {
            aspectRatio: 1,
            viewMode: 1,
            autoCropArea: 1,
        })
        URL.revokeObjectURL(imageUrl)
    }
    cropImage.src = imageUrl
    cropDialog.showModal()
}

fileInput?.addEventListener('change', () => {
    const [file] = fileInput.files
    if (!file) return
    if (!file.type.startsWith('image/')) {
        resetSelectedFile()
        return
    }

    openCropDialog(file)
})

clearInput?.addEventListener('change', () => {
    if (clearInput.checked) {
        fileInput.value = ''
        hidePreview()
    } else if (previewImage?.dataset.originalSrc) {
        showPreview(previewImage.dataset.originalSrc)
    }
})

applyCropButton?.addEventListener('click', applyCrop)
cancelCropButton?.addEventListener('click', () => {
    resetSelectedFile()
    closeCropDialog()
})

cropDialog?.addEventListener('cancel', (event) => {
    event.preventDefault()
    resetSelectedFile()
    closeCropDialog()
})

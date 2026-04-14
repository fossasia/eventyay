const setDisabledState = function(input, disabled) {
    if (!input) return
    input.disabled = disabled
    input.setAttribute('aria-disabled', disabled ? 'true' : 'false')
}

const setVisibleState = function(element, visible) {
    if (!element) return
    element.hidden = !visible
    element.style.display = visible ? '' : 'none'
}

const updatePreview = function(pair, url) {
    const preview = pair.querySelector('[data-image-url-preview]')
    const previewLink = pair.querySelector('[data-image-url-preview-link]')
    const previewImage = pair.querySelector('[data-image-url-preview-image]')
    const previewError = pair.querySelector('[data-image-url-preview-error]')

    if (!preview || !previewLink || !previewImage) return

    const normalizedUrl = url.trim()
    if (!normalizedUrl) {
        setVisibleState(preview, false)
        previewLink.removeAttribute('href')
        previewImage.removeAttribute('src')
        setVisibleState(previewImage, false)
        setVisibleState(previewError, false)
        return
    }

    setVisibleState(preview, true)
    previewLink.href = normalizedUrl
    setVisibleState(previewImage, true)
    if (previewImage.src !== normalizedUrl) {
        previewImage.src = normalizedUrl
    }
    setVisibleState(previewError, false)
}

const initImageSourcePair = function(pair) {
    const fileInput = document.getElementById(pair.dataset.fileInputId)
    const urlInput = document.getElementById(pair.dataset.urlInputId)

    if (!fileInput || !urlInput) return

    const clearCheckboxName = `${fileInput.name}-clear`
    const clearCheckbox = fileInput.form?.elements?.[clearCheckboxName] || null

    const syncState = function() {
        const urlValue = urlInput.value.trim()
        const hasUrl = urlValue.length > 0
        const hasSelectedFile = Boolean(fileInput.files && fileInput.files.length > 0)
        const hasCurrentFile = pair.dataset.hasCurrentFile === 'true' && !(clearCheckbox && clearCheckbox.checked)

        if (hasUrl && hasSelectedFile) {
            fileInput.value = ''
        }

        setDisabledState(fileInput, hasUrl)
        setDisabledState(clearCheckbox, hasUrl)
        setDisabledState(urlInput, !hasUrl && (hasSelectedFile || hasCurrentFile))
        updatePreview(pair, urlValue)
    }

    const previewImage = pair.querySelector('[data-image-url-preview-image]')
    const previewError = pair.querySelector('[data-image-url-preview-error]')
    if (previewImage) {
        previewImage.addEventListener('load', function() {
            setVisibleState(previewImage, true)
            setVisibleState(previewError, false)
        })
        previewImage.addEventListener('error', function() {
            if (!urlInput.value.trim()) return
            if (previewImage.complete && previewImage.naturalWidth > 0) {
                setVisibleState(previewError, false)
                return
            }
            setVisibleState(previewImage, false)
            setVisibleState(previewError, true)
        })
    }

    urlInput.addEventListener('input', syncState)
    fileInput.addEventListener('change', function() {
        if (fileInput.files && fileInput.files.length > 0) {
            urlInput.value = ''
        }
        syncState()
    })
    if (clearCheckbox) {
        clearCheckbox.addEventListener('change', syncState)
    }

    syncState()
}

const initImageSourceInputs = function() {
    document.querySelectorAll('[data-image-source-pair]').forEach(initImageSourcePair)
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initImageSourceInputs)
} else {
    initImageSourceInputs()
}

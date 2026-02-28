function setImage(url) {
    const image = document.querySelector('.avatar-form img');
    const imageWrapper = document.querySelector('.avatar-form .form-image-preview');
    const imageLink = imageWrapper.querySelector('a');
    image.src = url;
    imageLink.href = url;
    imageLink.dataset.lightbox = url;
    imageWrapper.classList.remove('d-none');
}

const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
};

const getErrorMessageElement = (form) => {
    let errorElement = form.querySelector('.file-validation-error');
    if (!errorElement) {
        const uploadDiv = form.querySelector('.avatar-upload');
        errorElement = document.createElement('div');
        errorElement.className = 'file-validation-error alert alert-danger mt-2 d-none';
        uploadDiv.parentNode.insertBefore(errorElement, uploadDiv.nextSibling);
    }
    return errorElement;
};

const clearFileError = (form) => {
    const errorElement = getErrorMessageElement(form);
    errorElement.textContent = '';
    errorElement.classList.add('d-none');
};

const showFileError = (form, message) => {
    const errorElement = getErrorMessageElement(form);
    errorElement.textContent = message;
    errorElement.classList.remove('d-none');
};

const validateImageFile = (file, maxSizeBytes) => {
    // Allowed image types
    const allowedTypes = ['image/png', 'image/jpeg', 'image/gif', 'image/jpg'];
    
    // Check file type
    if (!allowedTypes.includes(file.type)) {
        return {
            valid: false,
            error: 'Invalid file format. Only PNG, JPG, JPEG, and GIF images are allowed.'
        };
    }
    
    // Check file size
    if (file.size > maxSizeBytes) {
        const maxSizeFormatted = formatFileSize(maxSizeBytes);
        const fileSizeFormatted = formatFileSize(file.size);
        return {
            valid: false,
            error: `File size (${fileSizeFormatted}) exceeds the maximum allowed size of ${maxSizeFormatted}. Please choose a smaller image.`
        };
    }
    
    return { valid: true };
};

const updateFileInput = (ev) => {
    const form = ev.target.closest('.avatar-form');
    const imageSelected = ev.target.value !== '';

    if (imageSelected) {
        form.querySelector('input[type=checkbox]').checked = false;
        const files = ev.target.files;
        if (files && files.length > 0) {
            // Get max size from data attribute
            const maxSizeBytes = parseInt(ev.target.dataset.maxsize) || 10485760; // 10MB default
            
            // Validate file
            const validation = validateImageFile(files[0], maxSizeBytes);
            
            if (!validation.valid) {
                showFileError(form, validation.error);
                form.querySelector('.form-image-preview').classList.add('d-none');
                ev.target.value = ''; // Clear the input
                return;
            }
            
            clearFileError(form);
            
            const reader = new FileReader();
            reader.onload = (e) => setImage(e.target.result);
            reader.readAsDataURL(files[0]);
            form.querySelector('input[type=checkbox]').checked = false;
        } else if (form.querySelector('img').dataset.avatar) {
            clearFileError(form);
            setImage(form.querySelector('img').dataset.avatar);
            form.querySelector('input[type=checkbox]').checked = false;
        } else {
            form.querySelector('.form-image-preview').classList.add('d-none');
        }
    } else if (form.querySelector('img').dataset.avatar) {
        clearFileError(form);
        setImage(form.querySelector('img').dataset.avatar);
        form.querySelector('input[type=checkbox]').checked = false;
    } else {
        form.querySelector('.form-image-preview').classList.add('d-none');
    }
}

const updateCheckbox = (ev) => {
    if (ev.target.checked) {
        ev.target.closest('.avatar-form').querySelector('input[type=file]').value = '';
        ev.target.closest('.avatar-form').querySelector('.form-image-preview').classList.add('d-none');
    } else if (ev.target.closest('.avatar-form').querySelector('img').dataset.avatar) {
        setImage(ev.target.closest('.avatar-form').querySelector('img').dataset.avatar);
    } else {
        ev.target.closest('.avatar-form').querySelector('.form-image-preview').classList.add('d-none');
    }
}

const updateGravatarInput = async (ev) => {
    const checkbox = ev.target;
    const form = checkbox.closest('.avatar-form');
    const gravatarHash = form.querySelector('img').dataset.gravatar;
    const avatarUrl = form.querySelector('img').dataset.avatar;
    const imagePreview = form.querySelector('.form-image-preview');

    if (checkbox.checked) {
        const gravatarCheckUrl = `https://www.gravatar.com/avatar/${gravatarHash}?d=404`;
        const response = await fetch(gravatarCheckUrl);

        if (response.status === 404) {
            checkbox.checked = false;
            checkbox.disabled = true;
            const helpText = checkbox.parentElement.querySelector(".form-text")
            helpText.classList.add("text-warning")
            helpText.classList.remove("text-muted")
            checkbox.parentElement.querySelector("label").classList.add("text-muted")
        } else {
            form.querySelector('input[type=file]').value = '';
            setImage(`https://www.gravatar.com/avatar/${gravatarHash}?s=512`);
            form.querySelector(".avatar-upload").classList.add("d-none")
        }
    }
    if (!checkbox.checked) {
        form.querySelector(".avatar-upload").classList.remove("d-none")
        if (avatarUrl) {
            setImage(avatarUrl);
        } else {
            imagePreview.classList.add('d-none');
        }
    }
}

const initFileInput = function () {
    document.querySelectorAll(".avatar-form").forEach(form => {
        const preview = form.querySelector(".form-image-preview");
        // Don't remove the preview element - it needs to persist
        if (preview) {
            const img = preview.querySelector('img');
            if (img && !img.src) {
                preview.classList.add('d-none');
            }
        }
        
        document.querySelectorAll('.avatar-upload input[type=file]').forEach((element) => {
            element.addEventListener('change', updateFileInput)
        })
        document.querySelectorAll('#id_get_gravatar').forEach((checkbox) => {
            checkbox.addEventListener('change', updateGravatarInput)
        })
        document.querySelectorAll('.avatar-upload input[type=checkbox]').forEach((element) => {
            element.addEventListener('change', updateCheckbox)
        })
    })
}

onReady(initFileInput)

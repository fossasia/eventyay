/**
 * Meetup Quick-Create Interaction Module
 */

function findMatchingTimezoneOption(options, userTz) {
    if (!userTz || !options.length) {
        return null;
    }

    const directMatch = options.find((opt) => opt.value === userTz);
    if (directMatch) {
        return directMatch;
    }

    try {
        const canonicalUserTz = new Intl.DateTimeFormat(undefined, { timeZone: userTz }).resolvedOptions().timeZone;
        if (canonicalUserTz) {
            const canonicalMatch = options.find((opt) => {
                if (!opt.value) return false;
                if (opt.value === canonicalUserTz) return true;
                try {
                    return new Intl.DateTimeFormat(undefined, { timeZone: opt.value }).resolvedOptions().timeZone === canonicalUserTz;
                } catch {
                    return false;
                }
            });
            if (canonicalMatch) {
                return canonicalMatch;
            }
        }
    } catch {
        // Fall through if browser cannot resolve canonical identifier
    }

    try {
        const now = new Date();
        const sixMonths = new Date(now.getTime() + 182 * 24 * 60 * 60 * 1000);
        const userNow = now.toLocaleString('en-US', { timeZone: userTz, timeZoneName: 'short' });
        const userSixMonths = sixMonths.toLocaleString('en-US', { timeZone: userTz, timeZoneName: 'short' });
        const userRegion = userTz.includes('/') ? userTz.split('/')[0] : '';

        const regionalMatch = options.find((opt) => {
            if (!opt.value) return false;
            const optRegion = opt.value.includes('/') ? opt.value.split('/')[0] : '';
            if (userRegion && optRegion && optRegion !== userRegion) {
                return false;
            }
            try {
                return (
                    now.toLocaleString('en-US', { timeZone: opt.value, timeZoneName: 'short' }) === userNow &&
                    sixMonths.toLocaleString('en-US', { timeZone: opt.value, timeZoneName: 'short' }) === userSixMonths
                );
            } catch {
                return false;
            }
        });
        if (regionalMatch) {
            return regionalMatch;
        }

        return options.find((opt) => {
            if (!opt.value) return false;
            try {
                return (
                    now.toLocaleString('en-US', { timeZone: opt.value, timeZoneName: 'short' }) === userNow &&
                    sixMonths.toLocaleString('en-US', { timeZone: opt.value, timeZoneName: 'short' }) === userSixMonths
                );
            } catch {
                return false;
            }
        }) || null;
    } catch {
        return null;
    }
}

export function autoDetectTimezone() {
    const tzSelect = document.querySelector('select[name="basics-timezone"]');
    if (!tzSelect) {
        return;
    }

    try {
        const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        if (!userTz) {
            return;
        }

        const options = Array.from(tzSelect.options);
        const matchingOption = findMatchingTimezoneOption(options, userTz);

        if (matchingOption && !tzSelect.dataset.userSelected) {
            tzSelect.value = matchingOption.value;
            tzSelect.dispatchEvent(new Event('change', { bubbles: true }));
        }
    } catch (error) {
        console.warn('Could not auto-detect local timezone:', error);
    }

    tzSelect.addEventListener('change', () => {
        tzSelect.dataset.userSelected = 'true';
    });
}

export function initLocationToggles() {
    const physicalGroup = document.getElementById('physical-location-group');
    const virtualGroup = document.getElementById('virtual-video-group');
    const radios = document.querySelectorAll('input[name="basics-location_type"]');

    function updateLocationVisibility() {
        const checked = document.querySelector('input[name="basics-location_type"]:checked');
        const val = checked ? checked.value : 'in_person';

        if (val === 'in_person') {
            if (physicalGroup) physicalGroup.classList.remove('hidden');
            if (virtualGroup) virtualGroup.classList.add('hidden');
        } else if (val === 'virtual') {
            if (physicalGroup) physicalGroup.classList.add('hidden');
            if (virtualGroup) virtualGroup.classList.remove('hidden');
        } else if (val === 'hybrid') {
            if (physicalGroup) physicalGroup.classList.remove('hidden');
            if (virtualGroup) virtualGroup.classList.remove('hidden');
        }
    }

    radios.forEach((radio) => {
        radio.addEventListener('change', updateLocationVisibility);
    });

    updateLocationVisibility();
}

export function initCapacityToggles() {
    const limitGroup = document.getElementById('registration-limit-group');
    const radios = document.querySelectorAll('input[name="basics-capacity_type"]');

    function updateCapacityVisibility() {
        const checked = document.querySelector('input[name="basics-capacity_type"]:checked');
        const val = checked ? checked.value : 'unlimited';

        if (limitGroup) {
            if (val === 'limited') {
                limitGroup.classList.remove('hidden');
                const input = limitGroup.querySelector('input[name="basics-registration_limit"]');
                if (input && !input.value) {
                    input.focus();
                }
            } else {
                limitGroup.classList.add('hidden');
            }
        }
    }

    radios.forEach((radio) => {
        radio.addEventListener('change', updateCapacityVisibility);
    });

    updateCapacityVisibility();
}

export function initRegistrationFeeToggles() {
    const feeGroup = document.getElementById('registration-fee-group');
    const radios = document.querySelectorAll('input[name="basics-registration_fee_type"]');
    const pubKeyInput = document.querySelector('input[name="basics-payment_stripe_publishable_key"]');
    const secKeyInput = document.querySelector('input[name="basics-payment_stripe_secret_key"]');
    const indicator = document.getElementById('stripeStatusIndicator');
    const btnLabel = document.getElementById('stripeBtnLabel');
    const saveBtn = document.getElementById('stripeSaveBtn');

    function updateStripeStatus() {
        const hasKeys = Boolean(pubKeyInput && pubKeyInput.value.trim() && secKeyInput && secKeyInput.value.trim());
        if (indicator) {
            if (hasKeys) {
                indicator.classList.remove('hidden');
            } else {
                indicator.classList.add('hidden');
            }
        }
        if (btnLabel) {
            btnLabel.textContent = hasKeys ? 'Edit Stripe configuration' : 'Configure Stripe';
        }
    }

    function updateFeeVisibility() {
        const checked = document.querySelector('input[name="basics-registration_fee_type"]:checked');
        const val = checked ? checked.value : 'free';

        if (feeGroup) {
            if (val === 'paid') {
                feeGroup.classList.remove('hidden');
                const feeInput = feeGroup.querySelector('input[name="basics-registration_fee"]');
                if (feeInput && !feeInput.value) {
                    feeInput.focus();
                }
            } else {
                feeGroup.classList.add('hidden');
            }
        }
        updateStripeStatus();
    }

    radios.forEach((radio) => {
        radio.addEventListener('change', updateFeeVisibility);
    });

    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            updateStripeStatus();
            if (window.$ && window.$.fn && window.$.fn.modal) {
                window.$('#stripeConfigModal').modal('hide');
            }
        });
    }

    if (pubKeyInput) pubKeyInput.addEventListener('input', updateStripeStatus);
    if (secKeyInput) secKeyInput.addEventListener('input', updateStripeStatus);

    updateFeeVisibility();
}

function dismissModal(modalId) {
    if (window.$ && window.$.fn && window.$.fn.modal) {
        window.$('#' + modalId).modal('hide');
        return;
    }
    const modal = document.getElementById(modalId);
    if (!modal) return;
    const dismissBtn = modal.querySelector('[data-dismiss="modal"]');
    if (dismissBtn) {
        dismissBtn.click();
    }
}

export function initHeaderImagePicker() {
    const presetInput = document.querySelector('input[name="basics-header_image_preset"]');
    const fileInput = document.getElementById('id_basics-logo_image');
    const previewImg = document.getElementById('headerImagePreviewImg');
    const sourceBadge = document.getElementById('headerImageSourceBadge');
    const presetCards = document.querySelectorAll('.header-preset-card');
    const categoryPills = document.querySelectorAll('.preset-category-pill');
    const uploadDropzone = document.getElementById('headerUploadDropzone');
    const uploadBtn = document.getElementById('headerUploadBtn');
    const cropperSaveBtn = document.getElementById('cropperSaveBtn');

    if (!previewImg && !presetCards.length) {
        return;
    }

    let lastPresetId = presetInput ? presetInput.value : '';
    let lastPresetUrl = previewImg ? previewImg.src : '';
    let lastPresetName = sourceBadge ? sourceBadge.textContent : '';

    const getCustomUploadText = () => (window.gettext ? window.gettext('Custom upload') : 'Custom upload');

    // Category filter pills
    categoryPills.forEach((pill) => {
        pill.addEventListener('click', () => {
            const category = pill.dataset.category;
            categoryPills.forEach((p) => p.classList.remove('active'));
            pill.classList.add('active');

            presetCards.forEach((card) => {
                if (category === 'all' || card.dataset.category === category) {
                    card.style.display = '';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });

    function showPreviewImage(url, badgeText) {
        const placeholder = document.getElementById('headerImagePlaceholder');
        if (previewImg && url) {
            previewImg.src = url;
            previewImg.classList.remove('header-image-hidden');
            previewImg.style.display = 'block';
        }
        if (placeholder) {
            placeholder.classList.add('header-image-hidden');
            placeholder.style.display = 'none';
        }
        if (sourceBadge && badgeText) {
            sourceBadge.textContent = badgeText;
            sourceBadge.classList.remove('header-image-hidden');
            sourceBadge.style.display = '';
        }
    }

    // Preset card selection
    presetCards.forEach((card) => {
        card.addEventListener('click', () => {
            const presetId = card.dataset.presetId;
            const presetUrl = card.dataset.presetUrl;
            const presetName = card.dataset.presetName;

            lastPresetId = presetId;
            lastPresetUrl = presetUrl;
            lastPresetName = presetName;

            if (presetInput) {
                presetInput.value = presetId;
            }
            if (fileInput) {
                fileInput.value = '';
            }

            ['x', 'y', 'w', 'h'].forEach((coord) => {
                const hiddenCoord = document.getElementById(`id_basics-logo_image_crop_${coord}`);
                if (hiddenCoord) hiddenCoord.value = '';
            });

            if (presetUrl) {
                showPreviewImage(presetUrl, presetName);
            }

            presetCards.forEach((c) => c.classList.remove('active'));
            card.classList.add('active');

            dismissModal('headerImagePickerModal');
        });
    });

    // Custom upload dropzone
    function triggerFileInput() {
        if (fileInput) {
            fileInput.click();
        }
    }

    if (uploadDropzone) {
        uploadDropzone.addEventListener('click', triggerFileInput);

        uploadDropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadDropzone.classList.add('drag-over');
        });

        uploadDropzone.addEventListener('dragleave', () => {
            uploadDropzone.classList.remove('drag-over');
        });

        uploadDropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadDropzone.classList.remove('drag-over');
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0 && fileInput) {
                fileInput.files = e.dataTransfer.files;
                fileInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    }

    if (uploadBtn) {
        uploadBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            triggerFileInput();
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                const selectedFile = e.target.files[0];
                if (presetInput) {
                    presetInput.value = '';
                }
                presetCards.forEach((c) => c.classList.remove('active'));
                if (selectedFile && selectedFile.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = (evt) => {
                        if (evt.target && evt.target.result) {
                            showPreviewImage(evt.target.result, getCustomUploadText());
                        }
                    };
                    reader.readAsDataURL(selectedFile);
                }
                dismissModal('headerImagePickerModal');
            }
        });
    }

    // Restore previous preset if user closes/cancels cropper without cropping
    if (window.$) {
        window.$('#cropperModal').on('hidden.bs.modal', () => {
            if (!fileInput || !fileInput.value) {
                if (lastPresetId) {
                    if (presetInput) {
                        presetInput.value = lastPresetId;
                    }
                    if (lastPresetUrl) {
                        showPreviewImage(lastPresetUrl, lastPresetName);
                    }
                    presetCards.forEach((c) => {
                        if (c.dataset.presetId === lastPresetId) {
                            c.classList.add('active');
                        } else {
                            c.classList.remove('active');
                        }
                    });
                }
            }
        });
    }

    // Sync live preview when cropper applies
    if (cropperSaveBtn) {
        cropperSaveBtn.addEventListener('click', () => {
            setTimeout(() => {
                const cropperImage = document.getElementById('cropperImage');
                const fileContainer = fileInput ? fileInput.closest('.form-group') : null;
                const thumbImg = fileContainer ? fileContainer.querySelector('img') : null;
                let newSrc = null;
                if (thumbImg && thumbImg.src && previewImg && thumbImg !== previewImg) {
                    newSrc = thumbImg.src;
                } else if (cropperImage && cropperImage.src) {
                    newSrc = cropperImage.src;
                }
                if (newSrc) {
                    showPreviewImage(newSrc, getCustomUploadText());
                }
                if (presetInput) {
                    presetInput.value = '';
                }
                presetCards.forEach((c) => c.classList.remove('active'));
            }, 100);
        });
    }
}

function initMeetupCreate() {
    autoDetectTimezone();
    initLocationToggles();
    initCapacityToggles();
    initRegistrationFeeToggles();
    initHeaderImagePicker();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMeetupCreate);
} else {
    initMeetupCreate();
}

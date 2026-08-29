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

function initMeetupCreate() {
    autoDetectTimezone();
    initLocationToggles();
    initCapacityToggles();
    initRegistrationFeeToggles();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMeetupCreate);
} else {
    initMeetupCreate();
}

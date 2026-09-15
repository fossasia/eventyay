/**
 * Reveal-on-demand for SecretKeySettingsWidget fields.
 *
 * Flow:
 * 1. User clicks the "Show" button (.secret-reveal-btn) on a masked field.
 * 2. If the field shows '*****' (a saved-and-redacted secret), a password modal
 *    opens asking the admin to confirm their account password.
 * 3. On submit, the password is POSTed to the reveal-secret endpoint.
 * 4. On success, the real value is displayed in the input for AUTO_HIDE_SECONDS
 *    seconds, after which it automatically reverts to masked state.
 * 5. The "Show" button turns into "Hide" while the value is visible.
 * 6. If the field does NOT contain '*****' (user just typed a new password),
 *    a simple type toggle (password <-> text) is used without re-auth.
 */

const AUTO_HIDE_SECONDS = 30;
const REDACTED = '*****';

/** Returns the CSRF token from the Django csrftoken cookie. */
function getCsrfToken() {
    const name = 'csrftoken';
    const cookies = document.cookie.split(';');
    for (const cookie of cookies) {
        const [k, v] = cookie.trim().split('=');
        if (k === name) return decodeURIComponent(v);
    }
    const el = document.querySelector('[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
}

/** Get the reveal-secret endpoint URL from a data attribute on <body>. */
function getRevealUrl() {
    return document.body.dataset.revealSecretUrl || '/admin/global/settings/reveal-secret/';
}

// Per-field timer handles
const autoHideTimers = {};
const countdownIntervals = {};

function maskField(input, btn) {
    input.type = 'password';
    input.setAttribute('type', 'password');
    input.value = REDACTED;
    const icon = btn.querySelector('i');
    if (icon) { icon.classList.remove('fa-eye-slash'); icon.classList.add('fa-eye'); }
    btn.setAttribute('aria-pressed', 'false');
    btn.setAttribute('aria-label', btn.dataset.labelShow || 'Show secret key');
    btn.classList.remove('secret-toggle--revealed');
    const badge = btn.parentElement && btn.parentElement.querySelector('.secret-reveal-countdown');
    if (badge) badge.remove();
}

function revealField(input, btn, value) {
    const key = btn.dataset.key || '';
    input.type = 'text';
    input.setAttribute('type', 'text');
    input.value = value;
    const icon = btn.querySelector('i');
    if (icon) { icon.classList.remove('fa-eye'); icon.classList.add('fa-eye-slash'); }
    btn.setAttribute('aria-pressed', 'true');
    btn.setAttribute('aria-label', btn.dataset.labelHide || 'Hide secret key');
    btn.classList.add('secret-toggle--revealed');
    clearAutoHide(key);

    let badge = btn.parentElement && btn.parentElement.querySelector('.secret-reveal-countdown');
    if (!badge && btn.parentElement) {
        badge = document.createElement('span');
        badge.className = 'secret-reveal-countdown';
        // Inline styles to guarantee layout even if SCSS is aggressively cached
        badge.style.position = 'absolute';
        badge.style.right = '36px';
        badge.style.top = '50%';
        badge.style.transform = 'translateY(-50%)';
        badge.style.fontSize = '10px';
        badge.style.color = '#aaa';
        badge.style.pointerEvents = 'none';
        badge.style.whiteSpace = 'nowrap';
        badge.style.lineHeight = '1';
        
        btn.parentElement.appendChild(badge);
    }
    let remaining = AUTO_HIDE_SECONDS;
    if (badge) badge.textContent = remaining + 's';

    countdownIntervals[key] = setInterval(() => {
        remaining -= 1;
        if (badge) badge.textContent = remaining + 's';
        if (remaining <= 0) { clearInterval(countdownIntervals[key]); delete countdownIntervals[key]; }
    }, 1000);

    autoHideTimers[key] = setTimeout(() => {
        maskField(input, btn);
        delete autoHideTimers[key];
    }, AUTO_HIDE_SECONDS * 1000);
}

function clearAutoHide(key) {
    if (autoHideTimers[key]) { clearTimeout(autoHideTimers[key]); delete autoHideTimers[key]; }
    if (countdownIntervals[key]) { clearInterval(countdownIntervals[key]); delete countdownIntervals[key]; }
}

function getModal() {
    return document.getElementById('secret-reveal-modal');
}

function openModal() {
    const modal = getModal();
    if (!modal) return;
    const passwordInput = modal.querySelector('#secret-reveal-password');
    const errorEl = modal.querySelector('#secret-reveal-error');
    const confirmBtn = modal.querySelector('#secret-reveal-confirm');
    if (passwordInput) passwordInput.value = '';
    if (errorEl) { errorEl.textContent = ''; errorEl.hidden = true; }
    if (confirmBtn) confirmBtn.disabled = false;
    if (modal.showModal) { modal.showModal(); } else { modal.removeAttribute('hidden'); modal.style.display = ''; }
    if (passwordInput) setTimeout(() => passwordInput.focus(), 50);
}

function closeModal() {
    const modal = getModal();
    if (!modal) return;
    if (modal.close) { modal.close(); } else { modal.setAttribute('hidden', ''); }
}

function showModalError(message) {
    const modal = getModal();
    if (!modal) return;
    const errorEl = modal.querySelector('#secret-reveal-error');
    const confirmBtn = modal.querySelector('#secret-reveal-confirm');
    if (errorEl) { errorEl.textContent = message; errorEl.hidden = false; }
    if (confirmBtn) confirmBtn.disabled = false;
}

function waitForModalAction() {
    return new Promise((resolve, reject) => {
        const modal = getModal();
        if (!modal) { reject(new Error('Modal not found')); return; }
        const passwordInput = modal.querySelector('#secret-reveal-password');
        const confirmBtn = modal.querySelector('#secret-reveal-confirm');
        const cancelBtn = modal.querySelector('#secret-reveal-cancel');

        function cleanup() {
            if (confirmBtn) confirmBtn.removeEventListener('click', onConfirm);
            if (cancelBtn) cancelBtn.removeEventListener('click', onCancel);
            modal.removeEventListener('close', onCancel);
        }
        function onConfirm() {
            const pw = passwordInput ? passwordInput.value : '';
            cleanup();
            closeModal();
            resolve(pw);
        }
        function onCancel() {
            cleanup();
            closeModal();
            reject(new Error('cancelled'));
        }
        if (confirmBtn) confirmBtn.addEventListener('click', onConfirm, { once: true });
        if (cancelBtn) cancelBtn.addEventListener('click', onCancel, { once: true });
        modal.addEventListener('close', onCancel, { once: true });
    });
}

async function handleRevealClick(btn) {
    const wrapper = btn.closest('.secret-key-wrapper');
    if (!wrapper) return;
    const input = wrapper.querySelector('input');
    if (!input) return;
    const key = btn.dataset.key || '';

    // HIDE: already revealed
    if (btn.getAttribute('aria-pressed') === 'true') {
        clearAutoHide(key);
        maskField(input, btn);
        return;
    }

    // Non-redacted value: simple toggle, no re-auth needed
    if (input.value !== REDACTED) {
        input.type = 'text';
        input.setAttribute('type', 'text');
        const icon = btn.querySelector('i');
        if (icon) { icon.classList.remove('fa-eye'); icon.classList.add('fa-eye-slash'); }
        btn.setAttribute('aria-pressed', 'true');
        btn.setAttribute('aria-label', btn.dataset.labelHide || 'Hide secret key');
        return;
    }

    // Redacted value: step-up auth required
    openModal();
    let password;
    try {
        password = await waitForModalAction();
    } catch {
        return; // cancelled
    }

    if (!password) {
        openModal();
        showModalError('Please enter your password.');
        return;
    }

    // Set loading state on the button
    const modal = getModal();
    const confirmBtn = modal && modal.querySelector('#secret-reveal-confirm');
    const spinner = modal && modal.querySelector('#secret-reveal-spinner');
    const btnText = modal && modal.querySelector('#secret-reveal-btn-text');
    let originalText = 'Show secret';
    
    if (confirmBtn) confirmBtn.disabled = true;
    if (spinner) spinner.hidden = false;
    if (btnText) {
        originalText = btnText.textContent;
        btnText.textContent = 'Verifying...';
    }
    
    // Re-open modal so it stays visible while fetching
    if (modal) {
        if (modal.showModal && !modal.open) modal.showModal();
        else if (!modal.showModal) { modal.removeAttribute('hidden'); modal.style.display = ''; }
    }

    try {
        const resp = await fetch(getRevealUrl(), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCsrfToken(),
            },
            credentials: 'same-origin',
            body: new URLSearchParams({ key, password }),
        });

        const data = await resp.json().catch(() => ({}));

        // Reset loading state
        if (confirmBtn) confirmBtn.disabled = false;
        if (spinner) spinner.hidden = true;
        if (btnText) btnText.textContent = originalText;

        if (resp.ok && data.value) {
            closeModal();
            revealField(input, btn, data.value);
            return;
        }

        if (data.error === 'invalid_password') {
            // Keep modal open, show error
            showModalError(data.detail || 'Incorrect password. Please try again.');
            return;
        }
        
        closeModal();
        if (data.error === 'not_set') {
            alert(data.detail || 'No value is stored for this setting.');
            return;
        }
        if (data.error === 'no_password_backend') {
            alert(data.detail || 'Re-authentication is not supported for your account type.');
            return;
        }
        alert('An error occurred. Please try again.');
    } catch (err) {
        // Reset loading state
        if (confirmBtn) confirmBtn.disabled = false;
        if (spinner) spinner.hidden = true;
        if (btnText) btnText.textContent = originalText;
        closeModal();
        
        alert('Network error. Please check your connection and try again.');
        console.error('RevealSecretSetting fetch error:', err);
    }
}

function initSecretReveal() {
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.secret-toggle');
        if (!btn) return;
        e.preventDefault();
        handleRevealClick(btn);
    });
}

// Backwards-compat alias
function initSecretToggle() {
    initSecretReveal();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSecretReveal);
} else {
    initSecretReveal();
}

export { initSecretReveal, initSecretToggle };

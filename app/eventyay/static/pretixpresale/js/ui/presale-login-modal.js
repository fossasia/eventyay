const modal = document.getElementById('checkout-login-modal');
if (modal) {
    const i18n = modal.dataset;
    const loginBtn = document.getElementById('checkout-login-btn');
    const closeBtn = modal.querySelector('.checkout-login-close');
    const loginForm = document.getElementById('checkout-login-form');
    const errorDiv = document.getElementById('checkout-login-error');
    const nextUrlInput = document.getElementById('checkout-next-url');
    let checkoutUrl = '';

    // Constants for SSO popup
    const POPUP_WIDTH = 600;
    const POPUP_HEIGHT = 700;
    const POPUP_CHECK_INTERVAL = 500;
    let activeCheckLogin = null;

    // URL parameter name for redirect after login/register
    const REDIRECT_PARAM = 'next';

    // Open modal
    if (loginBtn) {
        loginBtn.addEventListener('click', (e) => {
            e.preventDefault();
            checkoutUrl = loginBtn.dataset.checkoutUrl || '';
            if (nextUrlInput) nextUrlInput.value = checkoutUrl;

            // Update SSO links with next URL
            const ssoLinks = modal.querySelectorAll('.checkout-sso-btn');
            ssoLinks.forEach((link) => {
                const url = new URL(link.href, window.location.origin);
                // Don't overwrite backend - it's already in the href from the template
                if (checkoutUrl) {
                    url.searchParams.set(REDIRECT_PARAM, checkoutUrl);
                }
                link.href = url.toString();
            });

            const registerLink = modal.querySelector('.checkout-login-footer a[href*="register"]');
            if (registerLink) {
                const url = new URL(registerLink.href, window.location.origin);
                url.searchParams.set(REDIRECT_PARAM, checkoutUrl);
                registerLink.href = url.toString();
            }

            // Clear any previous error state before showing the modal
            if (errorDiv) {
                errorDiv.textContent = '';
                errorDiv.style.display = 'none';
            }

            modal.style.display = 'flex';

            // Focus management for accessibility
            const firstInput = modal.querySelector('#checkout-email');
            if (firstInput) {
                // Use setTimeout to ensure modal is fully rendered
                setTimeout(() => firstInput.focus?.(), 100);
            }
        });
    }

    // Centralized function to close modal and cleanup
    const closeModal = () => {
        modal.style.display = 'none';
        // Clean up SSO popup interval if active
        if (activeCheckLogin) {
            clearInterval(activeCheckLogin);
            activeCheckLogin = null;
        }
        // Return focus to the button that opened the modal
        loginBtn?.focus();
    };

    // Close modal on close button click
    if (closeBtn) {
        closeBtn.addEventListener('click', closeModal);
    }

    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });

    // Close on Escape key - check if modal is visible using modal.style.display
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.style.display === 'flex') {
            closeModal();
        }
    });

    // AJAX form submission
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const submitBtn = document.getElementById('checkout-login-submit');
            if (!submitBtn) return;

            const originalChildNodes = [...submitBtn.childNodes].map(node =>
                node.cloneNode(true)
            );

            const setLoadingState = () => {
                submitBtn.disabled = true;
                submitBtn.replaceChildren();

                const spinner = document.createElement('i');
                spinner.className = 'fa fa-spinner fa-spin';
                spinner.setAttribute('aria-hidden', 'true');

                submitBtn.appendChild(spinner);
                submitBtn.append(' ', i18n.msgLoggingIn ?? '');
            };

            const resetButtonState = () => {
                submitBtn.disabled = false;
                submitBtn.replaceChildren(...originalChildNodes);
            };
            setLoadingState();

            if (errorDiv) errorDiv.style.display = 'none';

            const formData = new FormData(loginForm);

            try {
                const response = await fetch(loginForm.action, {
                    method: 'POST',
                    body: formData,
                    credentials: 'same-origin',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    redirect: 'manual'
                });

                // Login endpoint returns 302 on success (redirect: 'manual' prevents auto-follow)
                if (response.status === 302 || response.type === 'opaqueredirect') {
                    window.location.href = checkoutUrl;
                    return;
                }

                // 200 response from Django form means validation failed (invalid credentials)
                if (response.ok) {
                    if (errorDiv) {
                        errorDiv.textContent = i18n.msgInvalidCredentials ?? '';
                        errorDiv.style.display = 'block';
                    }
                } 
                // Server errors (5xx)
                else if (response.status >= 500) {
                    console.error('Server error during login:', response.status, response.statusText);
                    if (errorDiv) {
                        errorDiv.textContent = i18n.msgServerError ?? '';
                        errorDiv.style.display = 'block';
                    }
                } 
                // Other errors (4xx except handled cases, network issues, etc.)
                else {
                    console.error('Login failed with status:', response.status, response.statusText);
                    if (errorDiv) {
                        errorDiv.textContent = i18n.msgLoginFailed ?? '';
                        errorDiv.style.display = 'block';
                    }
                }
                
                resetButtonState();
            } catch (error) {
                // Network errors, timeouts, CORS issues, etc.
                console.error('Network error during login:', error);
                resetButtonState();
                if (errorDiv) {
                    errorDiv.textContent = i18n.msgConnectionFailed ?? '';
                    errorDiv.style.display = 'block';
                }
            }
        });
    }

    // Handle SSO popup login
    const ssoLinks = modal.querySelectorAll('.checkout-sso-btn');
    ssoLinks.forEach((link) => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const left = (window.innerWidth - POPUP_WIDTH) / 2;
            const top = (window.innerHeight - POPUP_HEIGHT) / 2;
            const popup = window.open(link.href, 'sso_login', `width=${POPUP_WIDTH},height=${POPUP_HEIGHT},left=${left},top=${top}`);

            if (!popup) {
                const popupErrorMessage = i18n.msgPopupBlocked ?? '';
                // Show error in the modal's error div
                if (errorDiv) {
                    errorDiv.textContent = popupErrorMessage;
                    errorDiv.style.display = 'block';
                }
                // Also show in a more prominent global error container / overlay
                const globalErrorDiv = document.getElementById('ajaxerr');
                if (globalErrorDiv) {
                    if (window.ajaxErrDialog && typeof window.ajaxErrDialog.show === 'function') {
                        window.ajaxErrDialog.show(popupErrorMessage);
                    } else {
                        globalErrorDiv.textContent = popupErrorMessage;
                        globalErrorDiv.style.display = 'block';
                        globalErrorDiv.setAttribute('role', 'alert');
                        globalErrorDiv.setAttribute('aria-live', 'assertive');
                        // Set tabindex to allow focus for screen reader announcement
                        globalErrorDiv.setAttribute('tabindex', '-1');
                        globalErrorDiv.focus();
                    }
                }
                return;
            }

            // Check if login was successful
            if (activeCheckLogin) clearInterval(activeCheckLogin);
            activeCheckLogin = setInterval(() => {
                try {
                    if (popup.closed) {
                        clearInterval(activeCheckLogin);
                        activeCheckLogin = null;
                        // Small delay to ensure session cookie is set before reload
                        setTimeout(() => {
                            window.location.href = checkoutUrl;
                        }, 300);
                    }
                } catch(e) {
                    // Cross-origin errors when checking popup.closed are expected
                    // Log for debugging but don't break the interval
                    console.debug('SSO popup check error (expected for cross-origin):', e.message);
                }
            }, POPUP_CHECK_INTERVAL);
        });
    });
}
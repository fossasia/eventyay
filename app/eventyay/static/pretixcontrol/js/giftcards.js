const activeTimeouts = new WeakMap();

/**
 * Resets the button and its icon back to their original state.
 *
 * @param {HTMLElement} btn - The copy button element.
 * @param {HTMLElement|null} icon - The icon element inside the button.
 */
const resetFeedback = (btn, icon) => {
    if (icon && 'originalClass' in icon.dataset) {
        icon.className = icon.dataset.originalClass;
        delete icon.dataset.originalClass;
    }

    if ('originalCaptured' in btn.dataset) {
        if (btn.dataset.originalAriaLabel) {
            btn.setAttribute('aria-label', btn.dataset.originalAriaLabel);
        } else {
            btn.removeAttribute('aria-label');
        }

        if ('originalTitle' in btn.dataset) {
            btn.setAttribute('title', btn.dataset.originalTitle);
            delete btn.dataset.originalTitle;
        } else {
            btn.removeAttribute('title');
        }

        if ('originalDataTitle' in btn.dataset) {
            btn.setAttribute('data-original-title', btn.dataset.originalDataTitle);
            delete btn.dataset.originalDataTitle;
        }

        delete btn.dataset.originalCaptured;
        delete btn.dataset.originalAriaLabel;
    }

    activeTimeouts.delete(btn);
};

/**
 * Applies visual and accessible feedback to the copy button and restores it after a timeout.
 *
 * @param {HTMLElement} btn - The copy button element.
 * @param {string} feedbackClass - The icon class to display (success or error).
 * @param {string} message - The message for aria-label and title.
 * @param {number} durationMs - How long before the feedback is reset.
 */
const setFeedback = (btn, feedbackClass, message, durationMs) => {
    const icon = btn.querySelector('i');
    if (icon && !('originalClass' in icon.dataset)) {
        icon.dataset.originalClass = icon.className;
    }

    if (!('originalCaptured' in btn.dataset)) {
        btn.dataset.originalCaptured = 'true';

        const originalLabel = btn.getAttribute('aria-label')
            || btn.getAttribute('data-original-title')
            || btn.getAttribute('title')
            || '';
        btn.dataset.originalAriaLabel = originalLabel;

        if (btn.hasAttribute('title')) {
            btn.dataset.originalTitle = btn.getAttribute('title');
        }
        if (btn.hasAttribute('data-original-title')) {
            btn.dataset.originalDataTitle = btn.getAttribute('data-original-title');
        }
    }

    if (icon) {
        icon.className = feedbackClass;
    }
    btn.setAttribute('aria-label', message);
    btn.setAttribute('title', message);

    if (activeTimeouts.has(btn)) {
        clearTimeout(activeTimeouts.get(btn));
    }

    const timeoutId = setTimeout(() => {
        resetFeedback(btn, icon);
    }, durationMs);
    activeTimeouts.set(btn, timeoutId);
};

/**
 * Fallback mechanism for copying text when navigator.clipboard is unavailable or rejected.
 * Selects the code element text and provides feedback to copy via keyboard.
 *
 * @param {HTMLElement} btn - The copy button element.
 */
const copyFallback = (btn) => {
    const codeEl = btn.closest('.gc-code-line')?.querySelector('.gc-code');
    if (codeEl) {
        const range = document.createRange();
        range.selectNodeContents(codeEl);
        const selection = window.getSelection();
        if (selection) {
            selection.removeAllRanges();
            selection.addRange(range);
        }
    }

    const failMsg = typeof gettext === 'function' ? gettext('Press Ctrl-C to copy!') : 'Press Ctrl-C to copy!';
    setFeedback(btn, 'fa fa-exclamation-circle text-danger', failMsg, 2500);
};

document.addEventListener('click', (event) => {
    const btn = event.target.closest('.gc-copy-btn');
    if (!btn) {
        return;
    }

    event.preventDefault();

    const text = btn.getAttribute('data-clipboard-text');
    if (!text) {
        return;
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            const successMsg = typeof gettext === 'function' ? gettext('Copied!') : 'Copied!';
            setFeedback(btn, 'fa fa-check text-success', successMsg, 1500);
        }).catch(() => {
            copyFallback(btn);
        });
    } else {
        copyFallback(btn);
    }
});

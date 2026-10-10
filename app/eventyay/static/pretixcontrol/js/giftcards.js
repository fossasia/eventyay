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
    const icon = btn.querySelector('i');
    if (icon) {
        const originalClass = icon.className;
        icon.className = 'fa fa-exclamation-circle text-danger';
        const originalTitle = btn.getAttribute('title') || '';
        const failMsg = typeof gettext === 'function' ? gettext('Press Ctrl-C to copy!') : 'Press Ctrl-C to copy!';
        btn.setAttribute('title', failMsg);
        setTimeout(() => {
            icon.className = originalClass;
            btn.setAttribute('title', originalTitle);
        }, 2500);
    }
};

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.gc-copy-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            const text = btn.getAttribute('data-clipboard-text');
            if (!text) {
                return;
            }

            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(() => {
                    const icon = btn.querySelector('i');
                    if (icon) {
                        const originalClass = icon.className;
                        icon.className = 'fa fa-check text-success';
                        setTimeout(() => {
                            icon.className = originalClass;
                        }, 1500);
                    }
                }).catch(() => {
                    copyFallback(btn);
                });
            } else {
                copyFallback(btn);
            }
        });
    });
});

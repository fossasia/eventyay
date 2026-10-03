document.addEventListener('DOMContentLoaded', () => {
    const selectAllCheckbox = document.querySelector('.gc-select-all');
    if (!selectAllCheckbox) {
        return;
    }

    const getRowCheckboxes = () => document.querySelectorAll('.gc-row-checkbox');

    const updateSelectAllState = () => {
        const rowCheckboxes = getRowCheckboxes();
        if (rowCheckboxes.length === 0) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
            return;
        }

        let checkedCount = 0;
        rowCheckboxes.forEach((cb) => {
            if (cb.checked) {
                checkedCount += 1;
            }
        });

        if (checkedCount === 0) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
        } else if (checkedCount === rowCheckboxes.length) {
            selectAllCheckbox.checked = true;
            selectAllCheckbox.indeterminate = false;
        } else {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = true;
        }
    };

    selectAllCheckbox.addEventListener('change', () => {
        const isChecked = selectAllCheckbox.checked;
        const rowCheckboxes = getRowCheckboxes();
        rowCheckboxes.forEach((cb) => {
            cb.checked = isChecked;
        });
    });

    document.addEventListener('change', (e) => {
        if (e.target && e.target.classList.contains('gc-row-checkbox')) {
            updateSelectAllState();
        }
    });

    document.querySelectorAll('.gc-copy-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            const text = btn.getAttribute('data-clipboard-text');
            if (text && navigator.clipboard && navigator.clipboard.writeText) {
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
                });
            }
        });
    });
});

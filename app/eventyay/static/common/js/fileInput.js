function handleFileInputChange(input) {
    const name = input.name;
    const selectedInfo = document.getElementById(`${name}-selected-info`);
    const selectedName = document.getElementById(`${name}-selected-name`);
    const savedInfo = document.getElementById(`${name}-saved-info`);
    const existingInfo = document.getElementById(`${name}-existing-info`);
    const preview = document.getElementById(`${name}-preview`);
    const clearCheckbox = document.getElementById(`${name}-clear-checkbox`);

    if (input.files?.[0]) {
        if (selectedName) selectedName.textContent = input.files[0].name;
        if (selectedInfo) selectedInfo.style.display = 'block';
        if (savedInfo) savedInfo.style.display = 'none';
        if (existingInfo) existingInfo.style.display = 'none';
        if (preview) preview.style.display = 'none';
        if (clearCheckbox) clearCheckbox.checked = false;
    } else {
        if (selectedInfo) selectedInfo.style.display = 'none';
        if (savedInfo) savedInfo.style.display = 'block';
    }
}

function clearFileInput(name) {
    const input = document.querySelector(`input[name="${name}"]`);
    if (input) input.value = '';
    const selectedInfo = document.getElementById(`${name}-selected-info`);
    if (selectedInfo) selectedInfo.style.display = 'none';
    const savedInfo = document.getElementById(`${name}-saved-info`);
    const existingInfo = document.getElementById(`${name}-existing-info`);
    const preview = document.getElementById(`${name}-preview`);
    // Only show saved/existing info if they exist in DOM (meaning there was a previous file)
    // Check if element exists and has meaningful content (not just whitespace)
    const savedStrong = savedInfo?.querySelector('strong');
    if (savedInfo && savedStrong?.textContent.trim()) {
        savedInfo.style.display = 'block';
    }
    const existingStrong = existingInfo?.querySelector('strong');
    if (existingInfo && existingStrong?.textContent.trim()) {
        existingInfo.style.display = 'block';
    }
    if (preview) preview.style.display = 'block';
}

function clearExistingFile(name) {
    const existingInfo = document.getElementById(`${name}-existing-info`);
    const preview = document.getElementById(`${name}-preview`);
    const clearCheckbox = document.getElementById(`${name}-clear-checkbox`);
    if (existingInfo) existingInfo.style.display = 'none';
    if (preview) preview.style.display = 'none';
    if (clearCheckbox) clearCheckbox.checked = true;
}

document.addEventListener('DOMContentLoaded', () => {
    // Auto-attach change handlers to file inputs
    document.querySelectorAll('.form-file-selected').forEach((el) => {
        const name = el.id.replace('-selected-info', '');
        const input = document.querySelector(`input[name="${name}"]`);
        if (input && !input.dataset.fileHandlerAttached) {
            input.dataset.fileHandlerAttached = 'true';
            input.addEventListener('change', () => handleFileInputChange(input));
        }
    });

    // Use event delegation for clear buttons with data attributes
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-clear-file]');
        if (btn) {
            e.preventDefault();
            clearFileInput(btn.dataset.clearFile);
        }
        const existingBtn = e.target.closest('[data-clear-existing]');
        if (existingBtn) {
            e.preventDefault();
            clearExistingFile(existingBtn.dataset.clearExisting);
        }
    });
});

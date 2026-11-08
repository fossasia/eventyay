const form = document.getElementById('organizer-request');
const slug = document.getElementById('id_slug');
const preview = document.getElementById('slug-preview');
const status = document.getElementById('slug-status');
let timer;
let controller;

async function checkAvailability(value) {
    controller = new AbortController();
    try {
        const url = new URL(form.dataset.slugUrl, window.location.origin);
        url.searchParams.set('slug', value);
        const response = await fetch(url, {signal: controller.signal});
        if (!response.ok) {
            console.error('Organiser short-form check failed:', response.status);
            if (slug.value === value) status.textContent = form.dataset.unavailable;
            return;
        }
        const result = await response.json();
        if (slug.value !== value) return;
        status.textContent = result.message;
        slug.setAttribute('aria-invalid', String(!result.available));
        slug.setCustomValidity(result.available ? '' : result.message);
    } catch (error) {
        if (error.name === 'AbortError') return;
        console.error('Unable to check organiser short-form availability:', error);
        if (slug.value === value) status.textContent = form.dataset.unavailable;
    }
}

function updateSlug() {
    clearTimeout(timer);
    controller?.abort();
    const value = slug.value;
    preview.textContent = `${form.dataset.siteUrl}/${value || 'your-short-form'}/`;
    slug.setCustomValidity('');
    slug.removeAttribute('aria-invalid');
    status.textContent = value ? form.dataset.checking : '';
    if (value) timer = setTimeout(() => checkAvailability(value), 250);
}

slug.addEventListener('input', updateSlug);
updateSlug();

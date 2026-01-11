document.addEventListener('DOMContentLoaded', function () {
    // Get CSRF token from Django template
    // Ideally this should be passed via data attribute or meta tag, but for now we read it from global or data attribute
    // Since we are moving this to external file, we rely on the CSRF token being available.
    // However, Django templates render CSRF token. The common pattern is to read it from cookie or meta tag.
    // But adhering to the previous logic, let's assume `csrftoken` variable was global? No, it was local const.
    // We need to fetch it from the cookie since we can't inject it here.

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    const csrftoken = getCookie('eventyay_csrftoken') || getCookie('csrftoken');

    // Initialize Sortable for drag-and-drop reordering
    const tbody = document.getElementById('speaker-tbody');
    if (tbody) {
        Sortable.create(tbody, {
            handle: '.drag-handle',
            animation: 150,
            onEnd: function (evt) {
                const speakerIds = Array.from(tbody.querySelectorAll('tr[data-speaker-id]'))
                    .map(row => parseInt(row.dataset.speakerId, 10));

                // Get URL from data attribute on tbody, or construct it if not present (requires data attribute on element)
                // The original code used a template tag for URL. We must pass this URL via data attribute now.
                const reorderUrl = tbody.dataset.reorderUrl;

                if (!reorderUrl) {
                    console.error('Missing data-reorder-url on tbody');
                    return;
                }

                fetch(reorderUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrftoken
                    },
                    body: JSON.stringify({ speaker_ids: speakerIds })
                })
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('HTTP error ' + response.status);
                        }
                        return response.json();
                    })
                    .then(data => {
                        if (data.status !== 'success') {
                            console.error('Failed to save speaker order:', data.message);
                        }
                    })
                    .catch(error => {
                        console.error('Error saving speaker order:', error);
                    });
            }
        });
    }

    // Handle featured checkbox toggle
    document.querySelectorAll('.featured-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            const url = this.dataset.featuredUrl;
            if (!url) {
                console.error('Missing data-featured-url on featured checkbox');
                return;
            }

            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                }
            })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('HTTP error ' + response.status);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.status === 'success') {
                        this.checked = data.is_featured;
                    } else {
                        this.checked = !this.checked;
                        console.error('Failed to update featured status:', data.message);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    this.checked = !this.checked;
                });
        });
    });
});

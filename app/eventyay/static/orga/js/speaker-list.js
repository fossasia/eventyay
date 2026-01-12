document.addEventListener('DOMContentLoaded', function () {
    
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

    const tbody = document.getElementById('speaker-tbody');
    if (tbody) {
        Sortable.create(tbody, {
            handle: '.drag-handle',
            animation: 150,
            onEnd: function (evt) {
                const speakerIds = Array.from(tbody.querySelectorAll('tr[data-speaker-id]'))
                    .map(row => parseInt(row.dataset.speakerId, 10));

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

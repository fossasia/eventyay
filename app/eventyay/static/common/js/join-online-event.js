// Shared join handler for ticket (presale) pages.
document.addEventListener('click', async (e) => {
    const closeButton = e.target.closest(
        '#join-online-close-button, #join-online-close-button-missing-config'
    );
    if (closeButton) {
        e.preventDefault();
        const modalId = closeButton.id === 'join-online-close-button'
            ? 'join-video-popupmodal'
            : 'join-video-popupmodal-missing-config';
        const modal = document.getElementById(modalId);
        if (modal) modal.setAttribute('hidden', 'true');
        document.body.classList.remove('has-join-popup');
        return;
    }

    const link = e.target.closest('.join-video-link');
    if (!link) return;
    
    e.preventDefault();
    const url = link.getAttribute('href');

    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        if (response.ok) {
            const json = await response.json();
            if (json.redirect_url) {
                window.location.href = json.redirect_url;
            } else if (json.login_url) {
                window.location.href = json.login_url;
            }
        } else if (response.status === 401) {
            const json = await response.json();
            if (json.login_url) {
                window.location.href = json.login_url;
            }
        } else {
            const text = await response.text();
            document.body.classList.add('has-join-popup');
            
            if (text === 'user_not_allowed') {
                const modal = document.getElementById('join-video-popupmodal');
                if (modal) modal.removeAttribute('hidden');
            } else if (text === 'missing_configuration') {
                const modal = document.getElementById('join-video-popupmodal-missing-config');
                if (modal) modal.removeAttribute('hidden');
            }
        }
    } catch (error) {
        console.error('Error joining video room:', error);
    }
});

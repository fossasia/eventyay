/**
 * Secret key toggle functionality using vanilla JavaScript
 * Handles password visibility toggle for secret key input fields
 */

function initSecretToggle() {
    // Use event delegation on document for dynamically added elements
    document.addEventListener('click', (e) => {
        const button = e.target.closest('.secret-toggle');
        if (!button) return;
        
        e.preventDefault();
        
        // Find the input field - check siblings within the wrapper
        const input = button.parentElement.querySelector('input[type="password"], input[type="text"]');
        const icon = button.querySelector('i');
        
        if (!input || !icon) return;
        
        // Get dynamic labels from data attributes
        const showLabel = button.dataset.labelShow || 'Show secret key';
        const hideLabel = button.dataset.labelHide || 'Hide secret key';
        
        // Toggle input type and update button state
        if (input.type === 'password') {
            input.type = 'text';
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
            button.setAttribute('aria-pressed', 'true');
            button.setAttribute('aria-label', hideLabel);
        } else {
            input.type = 'password';
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
            button.setAttribute('aria-pressed', 'false');
            button.setAttribute('aria-label', showLabel);
        }
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSecretToggle);
} else {
    initSecretToggle();
}

// Export for module usage
export { initSecretToggle };

function getPasswordToggleLabels() {
    const labelsEl = document.getElementById('password-toggle-labels');
    return labelsEl ? JSON.parse(labelsEl.textContent) : {};
}

export function autoWrapPasswordFields(root = document) {
    const passwordToggleLabels = getPasswordToggleLabels();
    
    root.querySelectorAll('input[type="password"]').forEach(input => {
        // Skip if already inside a .password-input-wrapper (e.g. signup form manual wraps)
        if (input.closest('.password-input-wrapper')) return;

        // Skip if we already wrapped it
        if (input.dataset.passwordWrapped === 'true') return;
        
        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'password-input-wrapper';
        
        // Wrap input
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);
        
        // Get translation string
        const showLabel = passwordToggleLabels.show || 'Show password';

        // Create toggle button
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'js-password-toggle';
        btn.setAttribute('aria-label', showLabel);
        btn.setAttribute('aria-pressed', 'false');
        btn.innerHTML = `
            <svg class="icon-eye" style="width: 20px; height: 20px; display: block;" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <svg class="icon-eye-slash" style="width: 20px; height: 20px; display: none;" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
            </svg>
        `;
        wrapper.appendChild(btn);
        
        input.dataset.passwordWrapped = 'true';
    });
}

export function initPasswordToggles(root = document) {
    autoWrapPasswordFields(root);

    root.querySelectorAll('.js-password-toggle').forEach(btn => {
        // Prevent multiple bindings if init is called multiple times
        if (btn.dataset.passwordToggleBound === 'true') return;
        
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const container = this.closest('.password-input-wrapper');
            if (!container) return;
            
            const input = container.querySelector('input');
            const iconEye = this.querySelector('.icon-eye');
            const iconEyeSlash = this.querySelector('.icon-eye-slash');
            
            if (input && iconEye && iconEyeSlash) {
                const passwordToggleLabels = getPasswordToggleLabels();
                const showLabel = passwordToggleLabels.show || 'Show password';
                const hideLabel = passwordToggleLabels.hide || 'Hide password';

                if (input.type === 'password') {
                    input.type = 'text';
                    iconEye.style.display = 'none';
                    iconEyeSlash.style.display = 'block';
                    btn.setAttribute('aria-pressed', 'true');
                    btn.setAttribute('aria-label', hideLabel);
                } else {
                    input.type = 'password';
                    iconEye.style.display = 'block';
                    iconEyeSlash.style.display = 'none';
                    btn.setAttribute('aria-pressed', 'false');
                    btn.setAttribute('aria-label', showLabel);
                }
            }
        });
        
        btn.dataset.passwordToggleBound = 'true';
    });
}

initPasswordToggles();

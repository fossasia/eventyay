document.addEventListener('DOMContentLoaded', function () {
    const loginForm = document.getElementById('login-form');
    const toggleLogin = document.getElementById('toggle-login');
    const collapseStateKey = 'loginFormCollapseState';

    // Restore state from localStorage
    if (loginForm) {
        const storedState = localStorage.getItem(collapseStateKey);
        if (storedState === 'open') {
            loginForm.classList.add('in');
        } else if (storedState === 'closed') {
            loginForm.classList.remove('in');
        }
    }

    // Save state on toggle
    if (toggleLogin && loginForm) {
        toggleLogin.addEventListener('click', function () {
            if (loginForm.classList.contains('in')) {
                localStorage.setItem(collapseStateKey, 'closed');
            } else {
                localStorage.setItem(collapseStateKey, 'open');
            }
        });
    }
});

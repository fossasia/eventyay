(function() {
    'use strict';
    
    const initStickyHeader = function() {
        const nav = document.getElementById('public-top-nav');
        const placeholder = document.getElementById('header-placeholder');
        
        if (nav && placeholder) {
            const triggerPoint = nav.offsetTop;
            
            window.addEventListener('scroll', function () {
                if (window.scrollY >= triggerPoint) {
                    nav.classList.add('is-sticky');
                    placeholder.classList.add('active');
                } else {
                    nav.classList.remove('is-sticky');
                    placeholder.classList.remove('active');
                }
            });
        }
    };
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initStickyHeader);
    } else {
        initStickyHeader();
    }
})();


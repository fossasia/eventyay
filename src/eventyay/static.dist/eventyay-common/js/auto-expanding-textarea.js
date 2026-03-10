(function () {
    'use strict';

    if (window.autoExpandTextareaInitialized) {
        return;
    }
    window.autoExpandTextareaInitialized = true;

    function autoExpandTextarea(textarea) {
        if (!textarea || textarea.hasAttribute('data-auto-expand-init')) return;
        textarea.setAttribute('data-auto-expand-init', 'true');

        function adjustHeight() {
            textarea.style.height = 'auto';
            requestAnimationFrame(function () {
                var computedStyle = window.getComputedStyle(textarea);
                var minHeight = parseInt(computedStyle.minHeight, 10) || 320;
                var viewportHeight = window.innerHeight;
                var computedMaxHeight = parseInt(computedStyle.maxHeight, 10);

                // Calculate offset based on viewport to prevent page scrollbar
                var offset = 500;
                if (viewportHeight < 600) {
                    offset = 300;
                } else if (viewportHeight < 800) {
                    offset = 400;
                } else if (viewportHeight < 1000) {
                    offset = 450;
                } else {
                    offset = 550;
                }

                var viewportBasedMax = Math.max(200, viewportHeight - offset);
                var maxHeight = Math.min(computedMaxHeight || 400, viewportBasedMax);
                var contentHeight = textarea.scrollHeight;
                var newHeight = Math.max(minHeight, Math.min(contentHeight, maxHeight));

                textarea.style.height = newHeight + 'px';
                textarea.style.overflowY = (contentHeight > maxHeight) ? 'auto' : 'hidden';
            });
        }

        textarea.addEventListener('input', adjustHeight);
        textarea.addEventListener('paste', function () { setTimeout(adjustHeight, 10); });

        adjustHeight();
    }

    function initializeAutoExpandTextareas() {
        var textareas = document.querySelectorAll('textarea[data-auto-expand="true"]');
        textareas.forEach(autoExpandTextarea);
    }

    // Single global resize listener to recalculate heights on viewport change
    var globalResizeTimeout;
    window.addEventListener('resize', function () {
        clearTimeout(globalResizeTimeout);
        globalResizeTimeout = setTimeout(initializeAutoExpandTextareas, 150);
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeAutoExpandTextareas);
    } else {
        initializeAutoExpandTextareas();
    }

    // Watch for dynamically added textareas (e.g., form fields added via AJAX)
    var formContainer = document.querySelector('form') || document.body;
    var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            mutation.addedNodes.forEach(function (node) {
                if (node.nodeType === 1) {
                    if (node.matches && node.matches('textarea[data-auto-expand="true"]')) {
                        autoExpandTextarea(node);
                    }
                    if (node.querySelectorAll) {
                        var textareas = node.querySelectorAll('textarea[data-auto-expand="true"]');
                        textareas.forEach(autoExpandTextarea);
                    }
                }
            });
        });
    });
    observer.observe(formContainer, { childList: true, subtree: true });
})();
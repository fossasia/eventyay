(function() {
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
            var computedStyle = window.getComputedStyle(textarea);
            var minHeight = parseInt(computedStyle.minHeight, 10) || 80;
            var maxHeight = parseInt(computedStyle.maxHeight, 10) || 300;
            var newHeight = Math.max(minHeight, Math.min(textarea.scrollHeight, maxHeight));
            textarea.style.height = newHeight + 'px';
            textarea.style.overflowY = (textarea.scrollHeight > maxHeight) ? 'auto' : 'hidden';
        }
        
        textarea.addEventListener('input', adjustHeight);
        textarea.addEventListener('paste', function() { setTimeout(adjustHeight, 10); });
        adjustHeight();
    }
    
    function initializeAutoExpandTextareas() {
        var textareas = document.querySelectorAll('textarea[data-auto-expand="true"]');
        textareas.forEach(function(textarea) {
            if (!textarea.hasAttribute('data-auto-expand-init')) {
                autoExpandTextarea(textarea);
            }
        });
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeAutoExpandTextareas);
    } else {
        initializeAutoExpandTextareas();
    }
    
    var formContainer = document.querySelector('form') || document.body;
    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
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
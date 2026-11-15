const timelineSteps = document.querySelectorAll('.dashboard-timeline .timeline-step');
if (timelineSteps.length) {
    function closeAllExcept(currentStep) {
        timelineSteps.forEach(function (step) {
            if (step !== currentStep) {
                step.classList.remove('is-open');
                step.classList.remove('is-closed');
                const content = step.querySelector('.timeline-step-content');
                if (content && content.hasAttribute('aria-expanded')) {
                    content.setAttribute('aria-expanded', 'false');
                }
            }
        });
    }

    timelineSteps.forEach(function (step) {
        const content = step.querySelector('.timeline-step-content');
        const menu = step.querySelector('.timeline-step-links');
        if (!menu) return;

        // Synchronize hover state with aria-expanded attribute
        step.addEventListener('mouseenter', function () {
            if (!step.classList.contains('is-closed') && content && content.hasAttribute('aria-expanded')) {
                content.setAttribute('aria-expanded', 'true');
            }
        });

        // Reset closed state when pointer leaves step so future hovers work
        step.addEventListener('mouseleave', function () {
            step.classList.remove('is-closed');
            if (!step.classList.contains('is-open') && content && content.hasAttribute('aria-expanded')) {
                content.setAttribute('aria-expanded', 'false');
            }
        });

        // Close when focus leaves the step
        step.addEventListener('focusout', function (e) {
            if (!step.contains(e.relatedTarget)) {
                step.classList.remove('is-open');
                step.classList.remove('is-closed');
                if (content && content.hasAttribute('aria-expanded')) {
                    content.setAttribute('aria-expanded', 'false');
                }
            }
        });

        // Click interaction: clicking the step trigger toggles open/closed
        if (content) {
            content.addEventListener('click', function (e) {
                if (menu) {
                    e.preventDefault();
                    const isVisible = step.classList.contains('is-open') || (!step.classList.contains('is-closed') && step.matches(':hover'));
                    if (isVisible) {
                        step.classList.remove('is-open');
                        step.classList.add('is-closed');
                        content.setAttribute('aria-expanded', 'false');
                    } else {
                        step.classList.add('is-open');
                        step.classList.remove('is-closed');
                        content.setAttribute('aria-expanded', 'true');
                        closeAllExcept(step);
                    }
                }
            });

            // Keyboard navigation on trigger
            content.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
                    e.preventDefault();
                    step.classList.add('is-open');
                    step.classList.remove('is-closed');
                    content.setAttribute('aria-expanded', 'true');
                    closeAllExcept(step);
                    const firstLink = menu.querySelector('a');
                    if (firstLink) firstLink.focus();
                } else if (e.key === 'Escape') {
                    step.classList.remove('is-open');
                    step.classList.add('is-closed');
                    content.setAttribute('aria-expanded', 'false');
                }
            });
        }

        // Keyboard navigation inside the menu
        menu.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                step.classList.remove('is-open');
                step.classList.add('is-closed');
                if (content) {
                    content.setAttribute('aria-expanded', 'false');
                    content.focus();
                }
            }
        });
    });

    // Close open menus when clicking anywhere outside
    document.addEventListener('click', function (e) {
        if (!e.target.closest('.dashboard-timeline')) {
            closeAllExcept(null);
        }
    });
}

/**
 * Interactive controller for the Talks Dashboard phase action dropdown menus.
 *
 * Implements:
 * - Hover state with graceful close delay (so pointers moving across the gap or items never lose menu).
 * - Click toggle so clicking a phase keeps its menu open until click-away.
 * - Keyboard navigation (Tab, Enter, Space, ArrowDown, Escape).
 * - ARIA state synchronization (aria-expanded).
 */
document.addEventListener('DOMContentLoaded', () => {
    const timeline = document.querySelector('.dashboard-timeline');
    if (!timeline) return;

    const stepsWithDropdown = Array.from(timeline.querySelectorAll('.timeline-step.has-dropdown'));
    if (!stepsWithDropdown.length) return;

    let closeTimer = null;
    let openStep = null;

    const setStepOpen = (step) => {
        if (closeTimer) {
            clearTimeout(closeTimer);
            closeTimer = null;
        }
        if (openStep && openStep !== step) {
            setStepClosed(openStep, true);
        }
        step.classList.add('is-open');
        openStep = step;
        const trigger = step.querySelector('.timeline-step-content');
        if (trigger) {
            trigger.setAttribute('aria-expanded', 'true');
        }
    };

    const setStepClosed = (step, immediate = false) => {
        const executeClose = () => {
            step.classList.remove('is-open');
            if (openStep === step) {
                openStep = null;
            }
            const trigger = step.querySelector('.timeline-step-content');
            if (trigger) {
                trigger.setAttribute('aria-expanded', 'false');
            }
        };

        if (immediate) {
            if (closeTimer) {
                clearTimeout(closeTimer);
                closeTimer = null;
            }
            executeClose();
        } else {
            if (closeTimer) {
                clearTimeout(closeTimer);
            }
            // 350ms graceful delay to allow natural pointer movement
            closeTimer = setTimeout(() => {
                executeClose();
                closeTimer = null;
            }, 350);
        }
    };

    stepsWithDropdown.forEach((step) => {
        const trigger = step.querySelector('.timeline-step-content');
        const dropdown = step.querySelector('.timeline-step-links');

        // Hover handling with graceful close delay
        step.addEventListener('mouseenter', () => {
            setStepOpen(step);
        });

        step.addEventListener('mouseleave', () => {
            setStepClosed(step, false);
        });

        // Click handling: toggle menu and prevent unintended action
        if (trigger) {
            trigger.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                if (step.classList.contains('is-open')) {
                    setStepClosed(step, true);
                } else {
                    setStepOpen(step);
                }
            });

            // Keyboard navigation on trigger
            trigger.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown') {
                    event.preventDefault();
                    setStepOpen(step);
                    const firstAction = dropdown?.querySelector('a');
                    if (firstAction) {
                        firstAction.focus();
                    }
                } else if (event.key === 'Escape') {
                    event.preventDefault();
                    setStepClosed(step, true);
                }
            });
        }

        // Dropdown keyboard handling
        if (dropdown) {
            dropdown.addEventListener('keydown', (event) => {
                if (event.key === 'Escape') {
                    event.preventDefault();
                    setStepClosed(step, true);
                    trigger?.focus();
                }
            });
        }
    });

    // Close when clicking outside
    document.addEventListener('click', (event) => {
        if (openStep && !openStep.contains(event.target)) {
            setStepClosed(openStep, true);
        }
    });

    // Close when pressing Escape globally
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && openStep) {
            const currentTrigger = openStep.querySelector('.timeline-step-content');
            setStepClosed(openStep, true);
            currentTrigger?.focus();
        }
    });
});

const initQuicksetupValidation = () => {
    const btnSaveContinue = document.querySelector(".btn-save-continue");
    if (!btnSaveContinue) return;

    const isVisible = (el) => el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects().length > 0;

    const focusElement = (el) => {
        if (!el) return;
        if (el.tabIndex === -1 && !el.hasAttribute('tabindex')) {
            el.setAttribute('tabindex', '-1');
        }
        el.focus({ preventScroll: true });
    };

    const scrollToTarget = (targetCard, controlToFocus) => {
        if (!targetCard) return;
        
        const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        const offsetTop = targetCard.getBoundingClientRect().top + window.scrollY - 80;

        window.scrollTo({
            top: offsetTop,
            behavior: prefersReducedMotion ? "auto" : "smooth"
        });

        if (!prefersReducedMotion) {
            targetCard.classList.add("highlight-pulse");
            setTimeout(() => {
                targetCard.classList.remove("highlight-pulse");
            }, 1200);
        }

        if (controlToFocus) {
            focusElement(controlToFocus);
        } else {
            focusElement(targetCard);
        }
    };

    // 1. Auto-scroll on page load if server validation failed
    const errors = Array.from(document.querySelectorAll(".has-error"));
    const firstError = errors.find(isVisible);
    
    let errorCard = null;
    let controlToFocus = null;

    if (firstError) {
        errorCard = firstError.closest(".quickstart-card");
        controlToFocus = firstError.querySelector("input:not([type='hidden']), select, textarea, button");
    }

    if (!errorCard) {
        const serverErrors = document.querySelector(".server-errors");
        if (serverErrors) {
            errorCard = document.querySelector("#step-review");
            controlToFocus = serverErrors;
        }
    }

    if (errorCard) {
        setTimeout(() => {
            scrollToTarget(errorCard, controlToFocus);
        }, 100);
    }

    // 2. Client-side validation on Save and continue
    btnSaveContinue.addEventListener("click", (e) => {
        let missingTarget = null;
        let control = null;

        // Check currency
        const currencySelect = document.querySelector("#id_currency");
        if (!currencySelect || !currencySelect.value.trim()) {
            missingTarget = document.querySelector("#step-currency");
            control = currencySelect;
        }

        // Check tickets
        if (!missingTarget) {
            let namedTickets = 0;
            const rows = document.querySelectorAll("#ticket-type-formset [data-formset-form]");
            rows.forEach(row => {
                const isDeleted = row.querySelector("input[name$='DELETE']")?.checked;
                if (!isDeleted && isVisible(row)) {
                    const nameInput = row.querySelector("input[name*='name']");
                    if (nameInput && nameInput.value.trim()) {
                        namedTickets++;
                    }
                }
            });
            if (namedTickets === 0) {
                missingTarget = document.querySelector("#step-tickets");
                const firstVisibleRow = Array.from(rows).find(r => 
                    isVisible(r) && !r.querySelector("input[name$='DELETE']")?.checked
                );
                if (firstVisibleRow) {
                    control = firstVisibleRow.querySelector("input[name*='name']");
                }
            }
        }

        // Check payment
        if (!missingTarget) {
            const reviewPaidTickets = document.querySelector("#review-paid-tickets");
            const paidTickets = reviewPaidTickets ? (parseInt(reviewPaidTickets.textContent, 10) || 0) : 0;
            const selectedMethods = document.querySelectorAll(".payment-tile input[type='checkbox']:checked").length;
            
            if (paidTickets > 0 && selectedMethods === 0) {
                missingTarget = document.querySelector("#step-payment");
                control = document.querySelector(".payment-tile input[type='checkbox']");
            }
        }

        if (missingTarget) {
            e.preventDefault();
            scrollToTarget(missingTarget, control);

            const serverErrorsBox = document.querySelector("#review-status-box .server-errors");
            if (serverErrorsBox) {
                serverErrorsBox.remove();
            }
        }
    });
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initQuicksetupValidation);
} else {
    initQuicksetupValidation();
}

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

    const getNamedTicketsCount = () => {
        let named = 0;
        const rows = document.querySelectorAll("#ticket-type-formset [data-formset-form]");
        rows.forEach(row => {
            const isDeleted = row.querySelector("input[name$='DELETE']")?.checked;
            if (!isDeleted && isVisible(row)) {
                const nameInput = row.querySelector("input[name*='name']");
                if (nameInput && nameInput.value.trim()) {
                    named++;
                }
            }
        });
        return named;
    };

    const getPaidTicketsCount = () => {
        let paid = 0;
        const rows = document.querySelectorAll("#ticket-type-formset [data-formset-form]");
        rows.forEach(row => {
            const isDeleted = row.querySelector("input[name$='DELETE']")?.checked;
            if (!isDeleted && isVisible(row)) {
                const priceInput = row.querySelector("input[name*='default_price']");
                if (priceInput) {
                    const priceStr = priceInput.value.trim().replace(",", ".");
                    const priceNum = parseFloat(priceStr);
                    if (!isNaN(priceNum) && priceNum > 0) {
                        paid++;
                    }
                }
            }
        });
        return paid;
    };

    const setPaymentCheckboxesAria = (hasError) => {
        const paymentCheckboxes = document.querySelectorAll(".payment-tile input[type='checkbox']");
        paymentCheckboxes.forEach(cb => {
            if (hasError) {
                cb.setAttribute("aria-invalid", "true");
                cb.setAttribute("aria-errormessage", "payment-error-msg");
            } else {
                cb.removeAttribute("aria-invalid");
                cb.removeAttribute("aria-errormessage");
            }
        });
    };

    const clearPaymentErrorIfFreeOrSelected = () => {
        const paymentCard = document.querySelector("#step-payment");
        if (!paymentCard) return;

        const paidCount = getPaidTicketsCount();
        const selectedCount = document.querySelectorAll(".payment-tile input[type='checkbox']:checked").length;

        // If both/all tickets price is 0 (or no paid tickets), or a payment method is selected, clear error
        if (paidCount === 0 || selectedCount > 0) {
            paymentCard.classList.remove("payment-error");
            setPaymentCheckboxesAria(false);
        }
    };

    // 1. Auto-scroll on page load ONLY if server validation failed
    const errors = Array.from(document.querySelectorAll(".has-error"));
    const firstError = errors.find(isVisible);
    const serverErrors = document.querySelector(".server-errors");

    let errorCard = null;
    let controlToFocus = null;

    if (firstError) {
        errorCard = firstError.closest(".quickstart-card");
        controlToFocus = firstError.querySelector("input:not([type='hidden']), select, textarea, button");
    }

    // Check payment validation state on load ONLY if server returned errors from submission
    const paidTickets = getPaidTicketsCount();
    const selectedMethods = document.querySelectorAll(".payment-tile input[type='checkbox']:checked").length;

    if (serverErrors && paidTickets > 0 && selectedMethods === 0) {
        const paymentCard = document.querySelector("#step-payment");
        if (paymentCard) {
            paymentCard.classList.add("payment-error");
            setPaymentCheckboxesAria(true);
        }
    }

    // Map server-side non-field validation errors to their corresponding steps
    if (!errorCard && serverErrors) {
        const namedTickets = getNamedTicketsCount();
        if (namedTickets === 0) {
            errorCard = document.querySelector("#step-tickets");
            const rows = document.querySelectorAll("#ticket-type-formset [data-formset-form]");
            const firstVisibleRow = Array.from(rows).find(r =>
                isVisible(r) && !r.querySelector("input[name$='DELETE']")?.checked
            );
            if (firstVisibleRow) {
                controlToFocus = firstVisibleRow.querySelector("input[name*='name']");
            }
        } else if (paidTickets > 0 && selectedMethods === 0) {
            errorCard = document.querySelector("#step-payment");
            controlToFocus = document.querySelector(".payment-tile input[type='checkbox']");
        } else {
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

        const paymentCard = document.querySelector("#step-payment");

        // Check currency
        const currencySelect = document.querySelector("#id_currency");
        if (!currencySelect || !currencySelect.value.trim()) {
            missingTarget = document.querySelector("#step-currency");
            control = currencySelect;
        }

        // Check tickets
        if (!missingTarget) {
            const namedTickets = getNamedTicketsCount();
            if (namedTickets === 0) {
                missingTarget = document.querySelector("#step-tickets");
                const rows = document.querySelectorAll("#ticket-type-formset [data-formset-form]");
                const firstVisibleRow = Array.from(rows).find(r => 
                    isVisible(r) && !r.querySelector("input[name$='DELETE']")?.checked
                );
                if (firstVisibleRow) {
                    control = firstVisibleRow.querySelector("input[name*='name']");
                }
            }
        }

        // Check payment: ONLY required if there are paid tickets
        const currentPaidTickets = getPaidTicketsCount();
        const currentSelectedMethods = document.querySelectorAll(".payment-tile input[type='checkbox']:checked").length;

        if (currentPaidTickets > 0 && currentSelectedMethods === 0) {
            if (paymentCard) {
                paymentCard.classList.add("payment-error");
            }
            setPaymentCheckboxesAria(true);
            if (!missingTarget) {
                missingTarget = paymentCard;
                control = document.querySelector(".payment-tile input[type='checkbox']");
            }
        } else {
            if (paymentCard) {
                paymentCard.classList.remove("payment-error");
            }
            setPaymentCheckboxesAria(false);
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

    // 3. Clear payment error dynamically when payment selection changes
    const paymentCard = document.querySelector("#step-payment");
    if (paymentCard) {
        paymentCard.addEventListener("change", (e) => {
            if (e.target.matches && e.target.matches("input[type='checkbox']")) {
                clearPaymentErrorIfFreeOrSelected();
            }
        });
    }

    const paymentCheckboxes = document.querySelectorAll(".payment-tile input[type='checkbox']");
    paymentCheckboxes.forEach(cb => {
        cb.addEventListener("change", clearPaymentErrorIfFreeOrSelected);
    });

    const paymentTiles = document.querySelectorAll(".payment-tile");
    paymentTiles.forEach(tile => {
        tile.addEventListener("click", () => {
            setTimeout(clearPaymentErrorIfFreeOrSelected, 10);
        });
    });

    // 4. Clear payment error dynamically when ticket price is 0 or paid tickets are deleted
    const ticketFormset = document.querySelector("#ticket-type-formset");
    if (ticketFormset) {
        ticketFormset.addEventListener("input", clearPaymentErrorIfFreeOrSelected);
        ticketFormset.addEventListener("change", clearPaymentErrorIfFreeOrSelected);
        ticketFormset.addEventListener("click", (e) => {
            if (e.target.closest("[data-formset-delete-button]")) {
                setTimeout(clearPaymentErrorIfFreeOrSelected, 10);
            }
        });
    }

    const formsetContainer = document.querySelector("[data-formset]");
    if (formsetContainer) {
        formsetContainer.addEventListener("formDeleted", () => {
            setTimeout(clearPaymentErrorIfFreeOrSelected, 10);
        });
        formsetContainer.addEventListener("formAdded", () => {
            setTimeout(clearPaymentErrorIfFreeOrSelected, 10);
        });
    }
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initQuicksetupValidation);
} else {
    initQuicksetupValidation();
}

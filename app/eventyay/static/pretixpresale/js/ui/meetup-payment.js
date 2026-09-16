/**
 * Meetup Card Payment Modal Validation, Stripe Elements, and Overlay Controller
 */

function initMeetupPayment() {
    const modal = document.getElementById('meetup-payment-modal');
    const form = document.querySelector('.meetup-payment-form');
    const openBtns = document.querySelectorAll('.open-meetup-payment-btn');

    if (!modal || !form) return;

    if (modal.parentElement !== document.body) {
        document.body.appendChild(modal);
    }

    const closeBtn = modal.querySelector('.meetup-payment-close');
    const cancelBtn = modal.querySelector('.meetup-payment-cancel');
    const cardNameInput = form.querySelector('#id_card_name');
    const tokenInput = form.querySelector('#id_stripe_token');
    const submitBtn = form.querySelector('#btnPayConfirm');
    const btnSpinner = submitBtn ? submitBtn.querySelector('.btn-spinner') : null;
    const btnText = submitBtn ? submitBtn.querySelector('.btn-text') : null;
    const originalBtnText = btnText ? btnText.textContent : 'Pay now';
    const errorAlert = form.querySelector('#meetupPaymentErrorAlert');
    const stripePublishableKey = form.dataset.stripePublishableKey || '';
    const msgNameRequired = form.dataset.msgNameRequired || 'Please enter your full name.';
    const msgEmailRequired = form.dataset.msgEmailRequired || 'Please enter a valid email address.';
    const msgUnavailable = form.dataset.msgUnavailable || 'Card payment is unavailable. Please refresh the page and try again.';
    const msgProcessing = form.dataset.msgProcessing || 'Processing payment...';
    const msgCardFailed = form.dataset.msgCardFailed || 'Card payment failed.';
    const msgError = form.dataset.msgError || 'Unable to process card details. Please try again.';
    const msgProcessingError = form.dataset.msgProcessingError || 'Payment processing error: ';

    let stripe = null;
    let elements = null;
    let cardNumber = null;
    let cardExpiry = null;
    let cardCvc = null;
    let elementsMounted = false;
    let isSubmitting = false;
    let paymentAttempt = 0;

    function setSubmitLoading(loading) {
        if (!submitBtn) return;
        submitBtn.disabled = loading;
        if (btnSpinner) {
            btnSpinner.classList.toggle('hidden', !loading);
        }
        if (btnText) {
            btnText.textContent = loading ? ` ${msgProcessing}` : originalBtnText;
        }
    }

    function initStripeElements() {
        if (elementsMounted || !stripePublishableKey || !window.Stripe) return;

        try {
            stripe = window.Stripe(stripePublishableKey);
            elements = stripe.elements();

            const elementStyles = {
                base: {
                    fontSize: '14px',
                    lineHeight: '20px',
                    color: '#333333',
                    fontFamily: '"Open Sans", "Helvetica Neue", Helvetica, Arial, sans-serif',
                    '::placeholder': {
                        color: '#999999',
                    },
                },
                invalid: {
                    color: '#a94442',
                    iconColor: '#a94442',
                },
            };

            const numEl = document.getElementById('stripe-card-number');
            const expEl = document.getElementById('stripe-card-expiry');
            const cvcEl = document.getElementById('stripe-card-cvc');

            if (numEl && expEl && cvcEl) {
                cardNumber = elements.create('cardNumber', { style: elementStyles });
                cardNumber.mount('#stripe-card-number');

                cardExpiry = elements.create('cardExpiry', { style: elementStyles });
                cardExpiry.mount('#stripe-card-expiry');

                cardCvc = elements.create('cardCvc', { style: elementStyles });
                cardCvc.mount('#stripe-card-cvc');

                elementsMounted = true;
            }
        } catch (err) {
            console.error('Failed to initialize Stripe Elements:', err);
        }
    }

    function openModal() {
        if (modal.parentElement !== document.body) {
            document.body.appendChild(modal);
        }
        modal.classList.remove('is-hidden');
        modal.style.display = 'flex';
        clearError();
        initStripeElements();
        const firstInput = form.querySelector('#id_attendee_name') || cardNameInput;
        if (firstInput) {
            setTimeout(() => {
                firstInput.focus();
            }, 100);
        }
    }

    function closeModal() {
        paymentAttempt += 1;
        isSubmitting = false;
        setSubmitLoading(false);
        modal.classList.add('is-hidden');
        modal.style.display = 'none';
    }

    openBtns.forEach((btn) => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            openModal();
        });
    });

    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !modal.classList.contains('is-hidden') && modal.style.display !== 'none') {
            closeModal();
        }
    });

    function showError(msg) {
        if (errorAlert) {
            errorAlert.textContent = msg;
            errorAlert.classList.remove('is-hidden');
            errorAlert.style.display = 'block';
        }
    }

    function clearError() {
        if (errorAlert) {
            errorAlert.textContent = '';
            errorAlert.classList.add('is-hidden');
            errorAlert.style.display = 'none';
        }
    }

    form.addEventListener('submit', (e) => {
        clearError();

        const nameInput = form.querySelector('#id_attendee_name');
        const emailInput = form.querySelector('#id_attendee_email');
        const cardName = cardNameInput ? cardNameInput.value.trim() : '';

        if (nameInput && !nameInput.value.trim()) {
            e.preventDefault();
            showError(msgNameRequired);
            nameInput.focus();
            return;
        }
        if (emailInput && !emailInput.value.trim()) {
            e.preventDefault();
            showError(msgEmailRequired);
            emailInput.focus();
            return;
        }

        if (tokenInput && tokenInput.value) {
            return; // Token already created, let form submit naturally
        }

        if (!stripe || !cardNumber || !tokenInput) {
            e.preventDefault();
            showError(msgUnavailable);
            return;
        }

        e.preventDefault();
        if (isSubmitting) return;
        isSubmitting = true;

        const attempt = ++paymentAttempt;
        setSubmitLoading(true);

        stripe
            .createToken(cardNumber, {
                name: cardName || (nameInput ? nameInput.value.trim() : ''),
            })
            .then((result) => {
                if (attempt !== paymentAttempt) return;

                if (result.error) {
                    showError(result.error.message || msgCardFailed);
                    isSubmitting = false;
                    setSubmitLoading(false);
                } else if (result.token && result.token.id) {
                    tokenInput.value = result.token.id;
                    form.submit();
                } else {
                    showError(msgError);
                    isSubmitting = false;
                    setSubmitLoading(false);
                }
            })
            .catch((err) => {
                if (attempt !== paymentAttempt) return;
                showError(`${msgProcessingError} ${err.message || err}`);
                isSubmitting = false;
                setSubmitLoading(false);
            });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMeetupPayment);
} else {
    initMeetupPayment();
}

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
    const errorAlert = form.querySelector('#meetupPaymentErrorAlert');
    const originalBtnHtml = submitBtn ? submitBtn.innerHTML : 'Pay now';
    const stripePublishableKey = form.dataset.stripePublishableKey || '';

    let stripe = null;
    let elements = null;
    let cardNumber = null;
    let cardExpiry = null;
    let cardCvc = null;
    let elementsMounted = false;
    let isSubmitting = false;
    let paymentAttempt = 0;

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
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnHtml;
        }
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
            showError('Please enter your full name.');
            nameInput.focus();
            return;
        }
        if (emailInput && !emailInput.value.trim()) {
            e.preventDefault();
            showError('Please enter a valid email address.');
            emailInput.focus();
            return;
        }

        if (tokenInput && tokenInput.value) {
            return; // Token already created, let form submit naturally
        }

        if (!stripe || !cardNumber || !tokenInput) {
            e.preventDefault();
            showError('Card payment is unavailable. Please refresh the page and try again.');
            return;
        }

        e.preventDefault();
        if (isSubmitting) return;
        isSubmitting = true;

        const attempt = ++paymentAttempt;

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="fa fa-circle-o-notch fa-spin"></span> Processing payment...';
        }

        stripe
            .createToken(cardNumber, {
                name: cardName || (nameInput ? nameInput.value.trim() : ''),
            })
            .then((result) => {
                if (attempt !== paymentAttempt) return;

                if (result.error) {
                    showError(result.error.message || 'Card payment failed.');
                    isSubmitting = false;
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = originalBtnHtml;
                    }
                } else if (result.token && result.token.id) {
                    tokenInput.value = result.token.id;
                    form.submit();
                } else {
                    showError('Unable to process card details. Please try again.');
                    isSubmitting = false;
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = originalBtnHtml;
                    }
                }
            })
            .catch((err) => {
                if (attempt !== paymentAttempt) return;

                showError('Payment processing error: ' + (err.message || err));
                isSubmitting = false;
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnHtml;
                }
            });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMeetupPayment);
} else {
    initMeetupPayment();
}

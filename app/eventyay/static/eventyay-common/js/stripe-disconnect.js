/**
 * Stripe Connect disconnect confirmation handler.
 * Attaches submit listeners to .stripe-disconnect-form to confirm account disconnection.
 */
function initStripeDisconnect() {
  const forms = document.querySelectorAll('.stripe-disconnect-form');
  forms.forEach(form => {
    form.addEventListener('submit', event => {
      const btn = event.submitter
        || form.querySelector('button[data-confirm]')
        || (form.id ? document.querySelector(`button[form="${form.id}"][data-confirm]`) : null);
      const message = btn ? btn.getAttribute('data-confirm') : 'Are you sure you want to disconnect this Stripe account?';
      if (!window.confirm(message)) {
        event.preventDefault();
      }
    });
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initStripeDisconnect);
} else {
  initStripeDisconnect();
}

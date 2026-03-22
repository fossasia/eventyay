/**
 * Tickets permission overlay: opens from .tickets-permission-link on any page that
 * includes fragment_tickets_permission_modal.html (no Bootstrap modal required).
 */

function getModal() {
  return document.getElementById('tickets-permission-modal');
}

function openModal() {
  const modal = getModal();
  if (!modal) {
    return;
  }
  // Main dashboard uses a Bootstrap modal for the same id; lazy-loaded widgets rely on delegation.
  if (modal.classList.contains('modal') && typeof window.jQuery !== 'undefined') {
    window.jQuery(modal).modal('show');
    return;
  }
  modal.classList.add('is-open');
  modal.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  const modal = getModal();
  if (!modal) {
    return;
  }
  modal.classList.remove('is-open');
  modal.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}

document.addEventListener('click', (event) => {
  const trigger = event.target.closest('.tickets-permission-link');
  if (trigger) {
    event.preventDefault();
    openModal();
    return;
  }

  const modal = getModal();
  if (!modal || !modal.classList.contains('is-open')) {
    return;
  }

  if (event.target === modal) {
    event.preventDefault();
    closeModal();
    return;
  }

  if (event.target.closest('#tickets-modal-ok-btn')) {
    closeModal();
  }
});

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') {
    return;
  }
  const modal = getModal();
  if (modal && modal.classList.contains('is-open')) {
    closeModal();
  }
});

/**
 * Open native <dialog> elements from buttons with data-toggle="dialog".
 */
export function initDialogTriggers(root = document) {
  const dialogTriggers = root.querySelectorAll('[data-toggle="dialog"]');
  for (const trigger of dialogTriggers) {
    if (trigger.dataset.dialogTriggerInit === 'true') {
      continue;
    }
    trigger.dataset.dialogTriggerInit = 'true';
    trigger.addEventListener('click', (event) => {
      event.preventDefault();
      const targetId =
        trigger.getAttribute('data-target') || trigger.getAttribute('data-dialog-target');
      if (!targetId) {
        return;
      }
      const dialog = root.querySelector(targetId);
      if (!dialog) {
        return;
      }
      if (typeof dialog.showModal === 'function') {
        dialog.showModal();
      } else {
        dialog.setAttribute('open', '');
      }
    });
  }

  const dialogForms = root.querySelectorAll('dialog form[method="dialog"]');
  for (const form of dialogForms) {
    if (form.dataset.dialogFormInit === 'true') {
      continue;
    }
    form.dataset.dialogFormInit = 'true';
    form.addEventListener('submit', (event) => {
      const parentDialog = form.closest('dialog');
      if (parentDialog && typeof parentDialog.close !== 'function') {
        event.preventDefault();
        parentDialog.removeAttribute('open');
      }
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => initDialogTriggers());
} else {
  initDialogTriggers();
}

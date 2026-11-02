const PANE_IDS = new Set(['tab-open-requests', 'tab-resolved-requests']);

function paneIdFromHash() {
  const id = (window.location.hash || '').replace(/^#/, '');
  return PANE_IDS.has(id) ? id : 'tab-open-requests';
}

function activate(root, paneId, updateHash) {
  root.querySelectorAll('[data-request-tab]').forEach((tab) => {
    const selected = tab.dataset.requestTab === paneId;
    tab.setAttribute('aria-selected', selected ? 'true' : 'false');
    tab.parentElement.classList.toggle('active', selected);
  });
  root.querySelectorAll('[data-request-pane]').forEach((pane) => {
    const selected = pane.id === paneId;
    pane.hidden = !selected;
  });
  if (updateHash) {
    history.replaceState(null, '', `#${paneId}`);
  }
}

document.querySelectorAll('[data-organizer-request-tabs]').forEach((root) => {
  activate(root, paneIdFromHash(), false);
  root.addEventListener('click', (event) => {
    const tab = event.target.closest('[data-request-tab]');
    if (!tab || !root.contains(tab)) {
      return;
    }
    event.preventDefault();
    activate(root, tab.dataset.requestTab, true);
  });
  window.addEventListener('hashchange', () => {
    activate(root, paneIdFromHash(), false);
  });
});

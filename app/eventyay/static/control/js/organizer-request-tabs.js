const PANE_IDS = new Set(['tab-open-requests', 'tab-resolved-requests']);
const PARENT_HASH = 'tab-organizer-requests';

function hashId() {
  return (window.location.hash || '').replace(/^#/, '');
}

function selectedPaneId(root) {
  const selected = root.querySelector('[data-request-tab][aria-selected="true"]');
  return selected?.dataset.requestTab || 'tab-open-requests';
}

function paneIdFromHash(root) {
  const id = hashId();
  if (PANE_IDS.has(id)) {
    return id;
  }
  if (id === PARENT_HASH) {
    return selectedPaneId(root);
  }
  return 'tab-open-requests';
}

function activate(root, paneId, updateHash) {
  root.querySelectorAll('[data-request-tab]').forEach((tab) => {
    const selected = tab.dataset.requestTab === paneId;
    tab.setAttribute('aria-selected', selected ? 'true' : 'false');
    tab.tabIndex = selected ? 0 : -1;
    tab.parentElement.classList.toggle('active', selected);
  });
  root.querySelectorAll('[data-request-pane]').forEach((pane) => {
    pane.hidden = pane.id !== paneId;
  });
  if (updateHash) {
    history.replaceState(null, '', `#${paneId}`);
  }
}

function bindKeyboard(root) {
  root.addEventListener('keydown', (event) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
      return;
    }
    const tab = event.target.closest('[data-request-tab]');
    if (!tab || !root.contains(tab)) {
      return;
    }
    const tabs = Array.from(root.querySelectorAll('[data-request-tab]'));
    const index = tabs.indexOf(tab);
    let next = index;
    if (event.key === 'ArrowRight') {
      next = (index + 1) % tabs.length;
    } else if (event.key === 'ArrowLeft') {
      next = (index - 1 + tabs.length) % tabs.length;
    } else if (event.key === 'Home') {
      next = 0;
    } else {
      next = tabs.length - 1;
    }
    event.preventDefault();
    activate(root, tabs[next].dataset.requestTab, true);
    tabs[next].focus();
  });
}

document.querySelectorAll('[data-organizer-request-tabs]').forEach((root) => {
  const initialId = hashId();
  activate(root, paneIdFromHash(root), initialId === PARENT_HASH);
  bindKeyboard(root);
  root.addEventListener('click', (event) => {
    const tab = event.target.closest('[data-request-tab]');
    if (!tab || !root.contains(tab)) {
      return;
    }
    event.preventDefault();
    activate(root, tab.dataset.requestTab, true);
  });
  window.addEventListener('hashchange', () => {
    const id = hashId();
    if (id === PARENT_HASH) {
      activate(root, selectedPaneId(root), true);
      return;
    }
    if (PANE_IDS.has(id)) {
      activate(root, id, false);
    }
  });
});

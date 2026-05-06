function initStartpageSidebar() {
  const body = document.body;
  const sidebar = document.getElementById('startpage-sidebar');
  const toggleButton = document.getElementById('sidebar-toggle');
  const backdrop = document.querySelector('.startpage-sidebar-backdrop');

  if (!sidebar || !toggleButton || !backdrop) {
    return;
  }

  function setSidebarOpen(isOpen) {
    body.classList.toggle('startpage-sidebar-open', isOpen);
    toggleButton.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    sidebar.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
    sidebar.toggleAttribute('inert', !isOpen);
    backdrop.hidden = !isOpen;
  }

  setSidebarOpen(false);

  toggleButton.addEventListener('click', function () {
    setSidebarOpen(!body.classList.contains('startpage-sidebar-open'));
  });

  backdrop.addEventListener('click', function () {
    setSidebarOpen(false);
  });

  document.addEventListener('click', function (event) {
    if (!body.classList.contains('startpage-sidebar-open')) {
      return;
    }
    if (sidebar.contains(event.target) || toggleButton.contains(event.target)) {
      return;
    }
    setSidebarOpen(false);
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      setSidebarOpen(false);
      toggleButton.focus();
    }
  });

  sidebar.addEventListener('click', function (event) {
    if (event.target.closest('a[href]')) {
      setSidebarOpen(false);
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initStartpageSidebar);
} else {
  initStartpageSidebar();
}

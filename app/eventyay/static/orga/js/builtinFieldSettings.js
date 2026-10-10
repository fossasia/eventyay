document.addEventListener('DOMContentLoaded', () => {
  const tabs = document.querySelectorAll('.lang-tab-btn');
  const activeLangInput = document.getElementById('active_lang');
  if (!tabs.length) return;

  function setLanguage(lang) {
    if (activeLangInput) {
      activeLangInput.value = lang;
    }
    tabs.forEach((tab) => {
      const isActive = tab.dataset.lang === lang;
      tab.classList.toggle('active', isActive);
      if (tab.parentElement) {
        tab.parentElement.classList.toggle('active', isActive);
      }
    });

    const inputs = document.querySelectorAll('.i18n-form-group input, .i18n-form-group textarea');
    inputs.forEach((el) => {
      if (el.getAttribute('lang') === lang) {
        el.classList.remove('d-none');
      } else {
        el.classList.add('d-none');
      }
    });
  }

  tabs.forEach((tab) => {
    tab.addEventListener('click', (e) => {
      e.preventDefault();
      setLanguage(tab.dataset.lang);
    });
  });

  const initialLang = activeLangInput ? activeLangInput.value : '';
  if (initialLang) {
    setLanguage(initialLang);
  }
});

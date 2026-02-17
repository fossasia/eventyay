(function () {
  'use strict';

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function () {
        return true;
      });
    }
    var helper = document.createElement('textarea');
    helper.value = text;
    helper.setAttribute('readonly', '');
    helper.style.position = 'absolute';
    helper.style.left = '-9999px';
    document.body.appendChild(helper);
    helper.select();
    var successful = document.execCommand('copy');
    document.body.removeChild(helper);
    return Promise.resolve(successful);
  }

  function initShareButtons() {
    var buttons = document.querySelectorAll('.startpage-event-share');
    if (!buttons.length) {
      return;
    }

    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        var url = button.dataset.url;
        if (!url) {
          return;
        }
        copyText(url)
          .then(function (ok) {
            if (ok) {
              button.classList.add('is-copied');
              window.setTimeout(function () {
                button.classList.remove('is-copied');
              }, 1600);
            }
          })
          .catch(function (error) {
            // eslint-disable-next-line no-console
            console.error(error);
          });
      });
    });
  }

  function initSearch() {
    var searchInput = document.getElementById('startpage-search-input');
    var resultsContainer = document.getElementById('startpage-search-results');
    if (!searchInput || !resultsContainer) {
      return;
    }

    function normalizeUrl(value) {
      if (!value) {
        return '';
      }
      var trimmed = value.trim();
      if (!trimmed) {
        return '';
      }
      try {
        var parsed = new URL(trimmed, window.location.origin);
        if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
          return parsed.href;
        }
      } catch (error) {
        // ignore invalid URLs
      }
      return '';
    }

    var emptyText = resultsContainer.dataset.emptyText || 'No matching events';
    var events = Array.from(document.querySelectorAll('.startpage-event-card')).map(function (card) {
      var link = card.querySelector('.startpage-event-title a');
      var date = card.querySelector('.startpage-event-date');
      var image = card.querySelector('.startpage-event-media img');
      return {
        name: (link ? link.textContent.trim() : '') || (card.dataset.eventName || ''),
        date: date ? date.textContent.trim() : '',
        url: (link ? link.href : '') || (card.dataset.eventUrl || ''),
        image: (image ? image.src : '') || (card.dataset.eventImage || '')
      };
    });

    function clearResults() {
      while (resultsContainer.firstChild) {
        resultsContainer.removeChild(resultsContainer.firstChild);
      }
    }

    function renderResults(items, query) {
      if (!query) {
        clearResults();
        resultsContainer.classList.remove('is-open');
        return;
      }
      var limited = items.slice(0, 6);
      clearResults();
      limited.forEach(function (item) {
        var safeUrl = normalizeUrl(item.url);
        var safeImage = normalizeUrl(item.image);
        var link = document.createElement('a');
        link.className = 'startpage-search-item';
        link.href = safeUrl || '#';
        link.setAttribute('role', 'option');
        if (!safeUrl) {
          link.setAttribute('aria-disabled', 'true');
          link.tabIndex = -1;
        }

        if (safeImage) {
          var img = document.createElement('img');
          img.src = safeImage;
          img.alt = '';
          img.setAttribute('aria-hidden', 'true');
          link.appendChild(img);
        } else {
          var placeholder = document.createElement('span');
          placeholder.className = 'startpage-search-placeholder';
          var icon = document.createElement('i');
          icon.className = 'fa fa-calendar';
          placeholder.appendChild(icon);
          link.appendChild(placeholder);
        }

        var textWrap = document.createElement('span');
        textWrap.className = 'startpage-search-text';

        var title = document.createElement('span');
        title.className = 'startpage-search-title';
        title.textContent = item.name;
        textWrap.appendChild(title);

        var dateText = document.createElement('span');
        dateText.className = 'startpage-search-date';
        dateText.textContent = item.date;
        textWrap.appendChild(dateText);

        link.appendChild(textWrap);
        resultsContainer.appendChild(link);
      });

      if (!limited.length) {
        var empty = document.createElement('div');
        empty.className = 'startpage-search-empty';
        empty.textContent = emptyText;
        resultsContainer.appendChild(empty);
      }
      resultsContainer.classList.add('is-open');
    }

    function filterEvents(query) {
      var needle = query.trim().toLowerCase();
      if (!needle) {
        renderResults([], '');
        return;
      }
      var matches = events.filter(function (eventItem) {
        return eventItem.name.toLowerCase().includes(needle);
      });
      renderResults(matches, needle);
    }

    searchInput.addEventListener('input', function (event) {
      filterEvents(event.target.value);
    });

    document.addEventListener('click', function (event) {
      if (!event.target.closest('.startpage-search')) {
        resultsContainer.classList.remove('is-open');
      }
    });
  }

  function initKeyboardShortcuts() {
    document.addEventListener('keydown', function (event) {
      if (event.target.matches('input, textarea, [contenteditable]')) {
        return;
      }
      if (
        !event.repeat &&
        event.key.toLowerCase() === 'k' &&
        (event.ctrlKey || event.metaKey) &&
        !(event.ctrlKey && event.metaKey) &&
        !event.shiftKey &&
        !event.altKey
      ) {
        var searchInput = document.getElementById('startpage-search-input');
        if (searchInput) {
          event.preventDefault();
          searchInput.focus();
        }
      }
    });
  }

  function init() {
    initShareButtons();
    initSearch();
    initKeyboardShortcuts();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

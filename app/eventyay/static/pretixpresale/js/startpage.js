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

    function renderResults(items, query) {
      if (!query) {
        resultsContainer.innerHTML = '';
        resultsContainer.classList.remove('is-open');
        return;
      }
      var limited = items.slice(0, 6);
      resultsContainer.innerHTML = limited
        .map(function (item) {
          return (
            '<a class="startpage-search-item" href="' + item.url + '" role="option">' +
            (item.image
              ? '<img src="' + item.image + '" alt="" aria-hidden="true" />'
              : '<span class="startpage-search-placeholder"><i class="fa fa-calendar"></i></span>') +
            '<span class="startpage-search-text">' +
            '<span class="startpage-search-title">' + item.name + '</span>' +
            '<span class="startpage-search-date">' + item.date + '</span>' +
            '</span>' +
            '</a>'
          );
        })
        .join('');

      if (!limited.length) {
        resultsContainer.innerHTML = '<div class="startpage-search-empty">' + emptyText + '</div>';
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

  function init() {
    initShareButtons();
    initSearch();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

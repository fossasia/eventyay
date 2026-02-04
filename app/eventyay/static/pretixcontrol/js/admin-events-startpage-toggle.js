(function () {
  'use strict';

  function getCookie(name) {
    var value = '; ' + document.cookie;
    var parts = value.split('; ' + name + '=');
    if (parts.length === 2) {
      return parts.pop().split(';').shift();
    }
    return '';
  }

  function resolveCsrfToken(table) {
    var csrfToken = table.getAttribute('data-startpage-csrf') || '';
    if (!csrfToken || csrfToken === 'NOTPROVIDED' || csrfToken.length < 32) {
      csrfToken = getCookie('csrftoken');
    }
    return csrfToken;
  }

  function handleToggleChange(toggle, table) {
    var url = table.getAttribute('data-startpage-toggle-url');
    if (!url) {
      return;
    }

    var eventId = toggle.getAttribute('data-event-id');
    var field = toggle.getAttribute('data-field');
    var previous = !toggle.checked;

    var payload = {
      event_id: eventId,
      field: field,
      value: toggle.checked
    };

    var relatedToggles = table.querySelectorAll('[data-event-id="' + eventId + '"]');
    relatedToggles.forEach(function (input) {
      input.disabled = true;
    });

    var headers = {
      'Content-Type': 'application/json'
    };

    var csrfToken = resolveCsrfToken(table);
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken;
    }

    fetch(url, {
      method: 'POST',
      headers: headers,
      credentials: 'same-origin',
      body: JSON.stringify(payload)
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok || !result.data || result.data.ok === false) {
          toggle.checked = previous;
          var message = (result.data && result.data.error) ? result.data.error : 'Unable to update start page settings.';
          window.alert(message);
          return;
        }

        var visibleToggle = document.getElementById('startpage-visible-' + eventId);
        var featuredToggle = document.getElementById('startpage-featured-' + eventId);
        if (visibleToggle) {
          visibleToggle.checked = !!result.data.startpage_visible;
        }
        if (featuredToggle) {
          featuredToggle.checked = !!result.data.startpage_featured;
        }
      })
      .catch(function () {
        toggle.checked = previous;
        window.alert('Unable to update start page settings.');
      })
      .finally(function () {
        relatedToggles.forEach(function (input) {
          input.disabled = false;
        });
      });
  }

  function init() {
    var table = document.querySelector('table[data-startpage-toggle-url]');
    if (!table) {
      return;
    }

    var toggles = table.querySelectorAll('.js-startpage-toggle');
    toggles.forEach(function (toggle) {
      toggle.addEventListener('change', function () {
        handleToggleChange(toggle, table);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

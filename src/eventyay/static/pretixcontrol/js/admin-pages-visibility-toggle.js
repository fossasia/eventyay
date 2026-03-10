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
    var csrfToken = table.getAttribute('data-pages-toggle-csrf') || '';
    if (!csrfToken || csrfToken === 'NOTPROVIDED' || csrfToken.length < 32) {
      csrfToken = getCookie('csrftoken');
    }
    return csrfToken;
  }

  function setLoadingState(toggles, isLoading) {
    toggles.forEach(function (input) {
      var toggle = input.closest('.toggle-switch');
      if (!toggle) {
        return;
      }
      if (isLoading) {
        toggle.classList.add('loading');
      } else {
        toggle.classList.remove('loading');
      }
    });
  }

  function applyServerState(pageId, data) {
    var startPageToggle = document.getElementById('page-startpage-' + pageId);
    var systemToggle = document.getElementById('page-system-' + pageId);

    if (startPageToggle && Object.prototype.hasOwnProperty.call(data, 'startpage')) {
      startPageToggle.checked = !!data.startpage;
    }
    if (systemToggle && Object.prototype.hasOwnProperty.call(data, 'system')) {
      systemToggle.checked = !!data.system;
    }
  }

  function handleToggleChange(toggle, table) {
    var url = toggle.getAttribute('data-toggle-url');
    if (!url) {
      return;
    }

    var pageId = toggle.getAttribute('data-page-id');
    var previous = !toggle.checked;

    var payload = {
      page_id: pageId,
      scope: toggle.getAttribute('data-scope'),
      value: toggle.checked
    };

    var relatedToggles = table.querySelectorAll('.js-page-visibility-toggle[data-page-id="' + pageId + '"]');
    var previousDisabledStates = [];
    relatedToggles.forEach(function (input) {
      previousDisabledStates.push(input.disabled);
      input.disabled = true;
    });
    setLoadingState(relatedToggles, true);

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
          var message = (result.data && result.data.error) ? result.data.error : 'Unable to update page visibility.';
          window.alert(message);
          return;
        }
        applyServerState(pageId, result.data);
        window.location.reload();
      })
      .catch(function () {
        toggle.checked = previous;
        window.alert('Unable to update page visibility.');
      })
      .finally(function () {
        relatedToggles.forEach(function (input, idx) {
          input.disabled = !!previousDisabledStates[idx];
        });
        setLoadingState(relatedToggles, false);
      });
  }

  function init() {
    var table = document.querySelector('table[data-pages-toggle-csrf]');
    if (!table) {
      return;
    }

    var toggles = table.querySelectorAll('.js-page-visibility-toggle');
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

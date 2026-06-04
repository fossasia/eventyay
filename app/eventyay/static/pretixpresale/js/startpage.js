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
    var dialog = document.getElementById('share-dialog');
    if (!buttons.length || !dialog) {
      return;
    }

    var closeBtn = document.getElementById('share-dialog-close');
    var facebookBtn = document.getElementById('share-facebook');
    var xBtn = document.getElementById('share-x');
    var linkedinBtn = document.getElementById('share-linkedin');
    var redditBtn = document.getElementById('share-reddit');
    var nativeBtn = document.getElementById('share-native');
    var urlInput = document.getElementById('share-url-input');
    if (!urlInput) {
      return;
    }
    var copyBtn = document.getElementById('share-copy-btn');
    var copiedLabel = copyBtn ? (copyBtn.dataset.copiedLabel || 'Copied!') : 'Copied!';
    var currentShareTitle = '';
    var originalCopyNodes = copyBtn ? Array.from(copyBtn.childNodes) : [];

    function resetCopyButton() {
      if (!copyBtn) {
        return;
      }
      copyBtn.classList.remove('is-copied');
      copyBtn.replaceChildren();
      for (var i = 0; i < originalCopyNodes.length; i++) {
        copyBtn.appendChild(originalCopyNodes[i].cloneNode(true));
      }
    }

    buttons.forEach(function (button) {
      var shareLabel = button.dataset.shareLabel || 'Share event';
      button.setAttribute('aria-label', shareLabel);
      button.setAttribute('title', shareLabel);

      button.addEventListener('click', function () {
        var url = button.dataset.url;
        if (!url) {
          return;
        }
        
        var eventCard = button.closest('.startpage-event-card');
        var title = eventCard ? eventCard.dataset.eventName : document.title;
        currentShareTitle = title;

        // Ensure relative URLs become absolute without rewriting absolute custom-domain URLs
        var absoluteUrlObject = new URL(url, window.location.origin);
        var shareImageSignature = button.dataset.shareImageSignature || '';
        if (shareImageSignature) {
          absoluteUrlObject.searchParams.set('si', shareImageSignature);
        }
        var absoluteUrl = absoluteUrlObject.href;
        resetCopyButton();

        // Set input value
        urlInput.value = absoluteUrl;

        // Set social URLs
        if (facebookBtn) {
          facebookBtn.href = 'https://www.facebook.com/sharer/sharer.php?u=' + encodeURIComponent(absoluteUrl);
        }
        if (xBtn) {
          xBtn.href = 'https://x.com/intent/tweet?url=' + encodeURIComponent(absoluteUrl) + '&text=' + encodeURIComponent(title);
        }
        if (linkedinBtn) {
          linkedinBtn.href = 'https://www.linkedin.com/shareArticle?mini=true&url=' + encodeURIComponent(absoluteUrl) + '&title=' + encodeURIComponent(title);
        }
        if (redditBtn) {
          redditBtn.href = 'https://www.reddit.com/submit?url=' + encodeURIComponent(absoluteUrl) + '&title=' + encodeURIComponent(title);
        }

        // Show dialog if it is not already open
        var isOpen = dialog.open || dialog.hasAttribute('open');
        if (!isOpen) {
          if (typeof dialog.showModal === 'function') {
            dialog.showModal();
          } else {
            dialog.setAttribute('open', '');
          }
        }
      });
    });

    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        if (typeof dialog.close === 'function') {
          dialog.close();
        } else {
          dialog.removeAttribute('open');
        }
      });
    }

    // Close when clicking backdrop
    if (!dialog.dataset.shareBackdropInit) {
      dialog.addEventListener('click', function (event) {
        if (event.target === dialog) {
          if (typeof dialog.close === 'function') {
            dialog.close();
          } else {
            dialog.removeAttribute('open');
          }
        }
      });
      dialog.dataset.shareBackdropInit = 'true';
    }

    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        var url = urlInput.value;
        if (!url) {
          return;
        }
        copyText(url)
          .then(function (ok) {
            if (ok) {
              copyBtn.classList.add('is-copied');
              copyBtn.replaceChildren(document.createTextNode(copiedLabel + ' '));
              var checkIcon = document.createElement('i');
              checkIcon.className = 'fa fa-check';
              checkIcon.setAttribute('aria-hidden', 'true');
              checkIcon.setAttribute('focusable', 'false');
              copyBtn.appendChild(checkIcon);
              window.setTimeout(function () {
                resetCopyButton();
              }, 1600);
            }
          })
          .catch(function (error) {
            // eslint-disable-next-line no-console
            console.error(error);
          });
      });
    }

    if (nativeBtn) {
      if (!navigator.share) {
        nativeBtn.style.display = 'none';
      } else {
        nativeBtn.addEventListener('click', function () {
          var url = urlInput.value;
          if (!url) {
            return;
          }
          navigator.share({
            title: currentShareTitle,
            url: url
          }).catch(function (error) {
            if (error && (error.name === 'AbortError' || error.name === 'NotAllowedError')) {
              return;
            }
            // eslint-disable-next-line no-console
            console.error('Error sharing:', error);
          });
        });
      }
    }
  }

  function initSearch() {
    var searchInput = document.getElementById('startpage-search-input');
    var resultsContainer = document.getElementById('startpage-search-results');
    if (!searchInput || !resultsContainer) {
      return;
    }

    var searchUrl = resultsContainer.dataset.searchUrl;
    if (!searchUrl) {
      return;
    }

    var emptyText = resultsContainer.dataset.emptyText || 'No matching events';
    var debounceTimer = null;
    var currentController = null;

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
      clearResults();
      items.forEach(function (item) {
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

      if (!items.length) {
        var empty = document.createElement('div');
        empty.className = 'startpage-search-empty';
        empty.textContent = emptyText;
        resultsContainer.appendChild(empty);
      }
      resultsContainer.classList.add('is-open');
    }

    function fetchResults(query) {
      var needle = query.trim();
      if (!needle) {
        clearResults();
        resultsContainer.classList.remove('is-open');
        return;
      }

      if (currentController) {
        currentController.abort();
      }
      currentController = new AbortController();

      fetch(searchUrl + '?format=json&q=' + encodeURIComponent(needle), { signal: currentController.signal })
        .then(function (response) {
          if (!response.ok) {
            clearResults();
            resultsContainer.classList.remove('is-open');
            return null;
          }
          return response.json();
        })
        .then(function (data) {
          if (data) {
            renderResults(data.results || [], needle);
          }
        })
        .catch(function (error) {
          if (error.name !== 'AbortError') {
            clearResults();
            resultsContainer.classList.remove('is-open');
            // eslint-disable-next-line no-console
            console.error('Search request failed:', error);
          }
        });
    }

    searchInput.addEventListener('input', function (event) {
      var value = event.target.value;
      clearTimeout(debounceTimer);
      if (!value.trim()) {
        clearResults();
        resultsContainer.classList.remove('is-open');
        return;
      }
      debounceTimer = setTimeout(function () {
        fetchResults(value);
      }, 300);
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

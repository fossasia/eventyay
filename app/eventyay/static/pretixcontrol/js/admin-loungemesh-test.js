function getCsrfToken() {
  const el = document.querySelector('[name=csrfmiddlewaretoken]');
  if (el && el.value) {
    return el.value;
  }
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [k, v] = cookie.trim().split('=');
    if (k === 'csrftoken') return decodeURIComponent(v);
  }
  return '';
}

function initLoungeMeshTest() {
  const testBtn = document.querySelector('[data-loungemesh-test-btn]');
  const resultContainer = document.querySelector('[data-loungemesh-test-result]');
  if (!testBtn || !resultContainer) {
    return;
  }

  testBtn.addEventListener('click', async (e) => {
    e.preventDefault();
    const testUrl = testBtn.getAttribute('data-test-url');
    if (!testUrl) {
      return;
    }

    const urlInput = document.getElementById('id_url');
    const secretInput = document.getElementById('id_api_secret');
    const serverId = testBtn.getAttribute('data-server-id') || '';

    const url = urlInput ? urlInput.value.trim() : '';
    const secret = secretInput ? secretInput.value.trim() : '';

    if (!url) {
      resultContainer.className = 'alert alert-warning';
      resultContainer.textContent = 'Please enter a server URL first.';
      resultContainer.classList.remove('hidden');
      if (urlInput) {
        urlInput.focus();
      }
      return;
    }

    resultContainer.className = 'alert alert-info';
    resultContainer.innerHTML = '<span class="fa fa-spinner fa-spin"></span> Testing connection to LoungeMesh server...';
    resultContainer.classList.remove('hidden');
    testBtn.disabled = true;

    try {
      const response = await fetch(testUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          url: url,
          api_secret: secret,
          server_id: serverId
        })
      });

      const data = await response.json();
      testBtn.disabled = false;
      if (data && data.ok) {
        resultContainer.className = 'alert alert-success';
        resultContainer.innerHTML = '<span class="fa fa-check-circle"></span> Connection successful! LoungeMesh server is reachable and service secret matches.';
      } else {
        resultContainer.className = 'alert alert-danger';
        const errorMsg = (data && data.message) ? data.message : 'Connection failed. Please verify the URL and EVENTYAY_SERVICE_SECRET.';
        resultContainer.innerHTML = '<span class="fa fa-exclamation-triangle"></span> ' + errorMsg;
      }
    } catch (err) {
      testBtn.disabled = false;
      resultContainer.className = 'alert alert-danger';
      resultContainer.innerHTML = '<span class="fa fa-exclamation-triangle"></span> Network error testing server: ' + (err.message || 'unknown error');
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLoungeMeshTest);
} else {
  initLoungeMeshTest();
}

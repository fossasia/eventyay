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

    if (!serverId && (!secret || secret.endsWith('*****'))) {
      resultContainer.className = 'alert alert-warning';
      resultContainer.textContent = 'Please enter an EVENTYAY_SERVICE_SECRET first.';
      resultContainer.classList.remove('hidden');
      if (secretInput) {
        secretInput.focus();
      }
      return;
    }

    resultContainer.className = 'alert alert-info';
    const spinner = document.createElement('span');
    spinner.className = 'fa fa-spinner fa-spin';
    resultContainer.replaceChildren(spinner, document.createTextNode(' Testing connection to LoungeMesh server...'));
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
          api_secret: (serverId && secret.endsWith('*****')) ? '*****' : secret,
          server_id: serverId
        })
      });

      const data = await response.json();
      testBtn.disabled = false;
      if (data && data.ok) {
        resultContainer.className = 'alert alert-success';
        const icon = document.createElement('span');
        icon.className = 'fa fa-check-circle';
        resultContainer.replaceChildren(icon, document.createTextNode(' Connection successful! LoungeMesh server is reachable and service secret matches.'));
      } else {
        resultContainer.className = 'alert alert-danger';
        const errorMsg = (data && data.message) ? data.message : 'Connection failed. Please verify the URL and EVENTYAY_SERVICE_SECRET.';
        const icon = document.createElement('span');
        icon.className = 'fa fa-exclamation-triangle';
        resultContainer.replaceChildren(icon, document.createTextNode(' ' + errorMsg));
      }
    } catch (err) {
      testBtn.disabled = false;
      resultContainer.className = 'alert alert-danger';
      const icon = document.createElement('span');
      icon.className = 'fa fa-exclamation-triangle';
      resultContainer.replaceChildren(icon, document.createTextNode(' Network error testing server: ' + (err.message || 'unknown error')));
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLoungeMeshTest);
} else {
  initLoungeMeshTest();
}

const panel = document.getElementById('recipient-list-panel')
if (panel) {
  const url = panel.dataset.recipientsUrl
  fetch(url, { credentials: 'same-origin' })
    .then((r) => r.json())
    .then((data) => {
      if (!data.recipients.length) {
        panel.innerHTML = '<p class="text-muted">No recipients found.</p>'
        return
      }
      const rows = data.recipients.map(
        (r) =>
          `<tr>
            <td>${r.email}</td>
            <td>${r.name}</td>
            <td>${r.sent ? '<span class="label label-success">Sent</span>' : '<span class="label label-danger">Failed</span>'}</td>
            <td>${r.error || ''}</td>
          </tr>`
      )
      panel.innerHTML =
        '<table class="table table-condensed">' +
        '<thead><tr><th>Email</th><th>Name</th><th>Status</th><th>Error</th></tr></thead>' +
        '<tbody>' + rows.join('') + '</tbody></table>' +
        (data.has_more ? '<p class="text-muted">More recipients not shown.</p>' : '')
    })
    .catch(() => {
      panel.innerHTML = '<p class="text-danger">Could not load recipient list.</p>'
    })
}

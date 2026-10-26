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
      const table = document.createElement('table')
      table.className = 'table table-condensed'
      table.innerHTML = '<thead><tr><th>Email</th><th>Name</th><th>Status</th><th>Error</th></tr></thead>'
      const body = document.createElement('tbody')
      for (const recipient of data.recipients) {
        const row = document.createElement('tr')
        for (const value of [recipient.email, recipient.name]) {
          const cell = document.createElement('td')
          cell.textContent = value ?? ''
          row.append(cell)
        }
        const statusCell = document.createElement('td')
        const status = document.createElement('span')
        status.className = recipient.sent ? 'label label-success' : 'label label-danger'
        status.textContent = recipient.sent ? 'Sent' : 'Failed'
        statusCell.append(status)
        const errorCell = document.createElement('td')
        errorCell.textContent = recipient.error || ''
        row.append(statusCell, errorCell)
        body.append(row)
      }
      table.append(body)
      panel.replaceChildren(table)
      if (data.has_more) {
        const notice = document.createElement('p')
        notice.className = 'text-muted'
        notice.textContent = 'More recipients not shown.'
        panel.append(notice)
      }
    })
    .catch((error) => {
      console.error('Could not load sent-email recipients', error)
      panel.innerHTML = '<p class="text-danger">Could not load recipient list.</p>'
    })
}

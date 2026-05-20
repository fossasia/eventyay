const pollInterval = 5000
const outboxSelector = '#sendmail-outbox-content'

async function refreshOutbox() {
  if (document.hidden) {
    return
  }

  const container = document.querySelector(outboxSelector)
  if (!container || container.contains(document.activeElement)) {
    return
  }

  try {
    const response = await fetch(window.location.href, {
      credentials: 'same-origin',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    })

    if (!response.ok) {
      console.error('Could not refresh sendmail outbox.', { status: response.status })
      return
    }

    const parsed = document.createElement('div')
    parsed.innerHTML = await response.text()

    const replacement = parsed.querySelector(outboxSelector)
    if (replacement) {
      container.replaceWith(replacement)
    }
  } catch (error) {
    console.error('Could not refresh sendmail outbox.', error)
  }
}

window.setInterval(refreshOutbox, pollInterval)

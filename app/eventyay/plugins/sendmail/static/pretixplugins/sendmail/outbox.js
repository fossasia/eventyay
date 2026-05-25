const pollInterval = 5000
const outboxSelector = '[data-outbox-refresh], #sendmail-outbox-content'

function getReplacementSelector(container) {
  if (container.id) {
    return `#${container.id}`
  }
  return '[data-outbox-refresh]'
}

function getRefreshContainers() {
  return Array.from(document.querySelectorAll(outboxSelector))
}

async function refreshOutbox() {
  if (document.hidden) {
    return
  }

  const containers = getRefreshContainers()
  if (!containers.length || containers.some((container) => container.contains(document.activeElement))) {
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

    containers.forEach((container) => {
      const replacement = parsed.querySelector(getReplacementSelector(container))
      if (replacement) {
        container.replaceWith(replacement)
      }
    })
  } catch (error) {
    console.error('Could not refresh sendmail outbox.', error)
  }
}

window.setInterval(refreshOutbox, pollInterval)

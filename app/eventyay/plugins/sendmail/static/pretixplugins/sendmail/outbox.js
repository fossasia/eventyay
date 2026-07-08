const pollInterval = 5000
const slowPollInterval = 30000
const outboxSelector = '[data-outbox-refresh], #sendmail-outbox-content'
let currentInterval = null

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

    const updatedContainer = document.querySelector('[data-pending-mail-count]')
    const pendingCount = updatedContainer ? parseInt(updatedContainer.dataset.pendingMailCount, 10) : 0
    adjustPolling(pendingCount)
  } catch (error) {
    console.error('Could not refresh sendmail outbox.', error)
  }
}

function adjustPolling(pendingCount) {
  const interval = pendingCount > 0 ? pollInterval : slowPollInterval
  if (currentInterval && currentInterval.expected !== interval) {
    clearInterval(currentInterval.id)
    currentInterval = { id: window.setInterval(refreshOutbox, interval), expected: interval }
  }
}

const initialContainer = document.querySelector('[data-pending-mail-count]')
const initialPendingCount = initialContainer ? parseInt(initialContainer.dataset.pendingMailCount, 10) : 0
const initialInterval = initialPendingCount > 0 ? pollInterval : slowPollInterval
currentInterval = { id: window.setInterval(refreshOutbox, initialInterval), expected: initialInterval }

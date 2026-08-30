const handleFeaturedChange = (element) => {
    const statusWrapper = element.closest("td")
    if (!statusWrapper) {
        return
    }
    const resetStatus = () => {
        statusWrapper.querySelectorAll("i.working, i.done, i.fail").forEach((icon) => {
            icon.classList.add("d-none")
        })
    }
    const setStatus = (statusName) => {
        const statusIcon = statusWrapper.querySelector("." + statusName)
        if (!statusIcon) {
            return
        }
        resetStatus()
        statusIcon.classList.remove("d-none")

        if (statusWrapper.resetTimeout) {
            clearTimeout(statusWrapper.resetTimeout)
        }
        statusWrapper.resetTimeout = setTimeout(resetStatus, 3000)
    }
    const fail = () => {
        element.checked = !element.checked
        setStatus("fail")
    }

    setStatus("working")

    const url = element.dataset.url
    if (!url) {
        fail()
        return
    }
    const options = {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("eventyay_csrftoken"),
        },
        credentials: "include",
    }

    fetch(url, options)
        .then((response) => {
            if (response.status === 200) {
                setStatus("done")
            } else {
                fail()
            }
        })
        .catch((error) => fail())
}

const initScrollPosition = () => {
    document.querySelectorAll(".keep-scroll-position").forEach((el) => {
        el.addEventListener("click", () => {
            sessionStorage.setItem("scroll-position", window.scrollY)
        })
    })
    const oldScrollY = sessionStorage.getItem("scroll-position")
    if (oldScrollY) {
        window.scroll(window.scrollX, Math.max(oldScrollY, window.innerHeight))
        sessionStorage.removeItem("scroll-position")
    }
}

const getCookie = (name) => {
    let cookieValue = null
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";")
        for (var i = 0; i < cookies.length; i++) {
            let cookie = cookies[i].trim()
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === name + "=") {
                cookieValue = decodeURIComponent(
                    cookie.substring(name.length + 1),
                )
                break
            }
        }
    }
    return cookieValue
}

const initFeaturedToggles = (root = document) => {
    root
        .querySelectorAll("input.submission_featured")
        .forEach((element) =>
            element.addEventListener("change", () =>
                handleFeaturedChange(element),
            ),
        )
}

onReady(() => {
    initScrollPosition()
    initFeaturedToggles()
})

// Re-bind featured toggles inside table regions replaced by AJAX filters.
document.addEventListener("eventyay:ajax-results-replaced", (event) => {
    initFeaturedToggles(event.detail?.container ?? document)
})


// Feedback Bulk Actions
const SELECTORS = {
  form: '.feedback-bulk-form',
  toggleAll: 'input[data-toggle-table]',
  rowCheckbox: 'input.feedback-batch-select-checkbox',
  batchActions: '.batch-select-actions-feedback',
  countLabel: '[data-batch-count-label]',
  actionButton: '[data-batch-action]',
  actionHint: '[data-batch-action-hint]',
}

const getSelectedCheckboxes = (form) =>
  Array.from(form.querySelectorAll(SELECTORS.rowCheckbox)).filter((checkbox) => checkbox.checked)

const updateBatchActions = (form) => {
  const batchActions = form.querySelector(SELECTORS.batchActions)
  if (!batchActions) {
    return
  }

  const checkboxes = Array.from(form.querySelectorAll(SELECTORS.rowCheckbox))
  const selected = getSelectedCheckboxes(form)
  const toggleAll = form.querySelector(SELECTORS.toggleAll)
  const countLabel = batchActions.querySelector(SELECTORS.countLabel)
  const actionButtons = Array.from(batchActions.querySelectorAll(SELECTORS.actionButton))
  const actionHint = batchActions.querySelector(SELECTORS.actionHint)
  const reasonNone = batchActions.dataset.batchDisabledReasonNone || ''
  const hasSelection = selected.length > 0

  if (countLabel) {
    const baseLabel = countLabel.dataset.baseLabel || countLabel.textContent.trim()
    countLabel.textContent = hasSelection ? `${baseLabel} (${selected.length})` : baseLabel
  }

  if (toggleAll) {
    toggleAll.indeterminate = hasSelection && selected.length < checkboxes.length
    toggleAll.checked = checkboxes.length > 0 && selected.length === checkboxes.length
  }

  actionButtons.forEach((button) => {
    button.disabled = !hasSelection
    if (!hasSelection && reasonNone) {
      button.title = reasonNone
    } else {
      button.removeAttribute('title')
    }
  })

  if (actionHint) {
    if (!hasSelection && reasonNone) {
      actionHint.textContent = reasonNone
      actionHint.hidden = false
    } else {
      actionHint.textContent = ''
      actionHint.hidden = true
    }
  }

  batchActions.classList.toggle('batch-select-actions-disabled', !hasSelection)
}

const initFeedbackBulkActions = (root = document) => {
  root.querySelectorAll(SELECTORS.form).forEach((form) => {
    if (form.dataset.feedbackBulkActionsInit === 'true') {
      return
    }
    form.dataset.feedbackBulkActionsInit = 'true'

    const toggleAll = form.querySelector(SELECTORS.toggleAll)
    if (toggleAll) {
      toggleAll.addEventListener('change', () => {
        const checked = toggleAll.checked
        form.querySelectorAll(SELECTORS.rowCheckbox).forEach((checkbox) => {
          checkbox.checked = checked
        })
        updateBatchActions(form)
      })
    }

    form.querySelectorAll(SELECTORS.rowCheckbox).forEach((checkbox) => {
      checkbox.addEventListener('change', () => updateBatchActions(form))
    })

    form.querySelectorAll(`${SELECTORS.actionButton}[value="delete"]`).forEach((button) => {
      button.addEventListener('click', (event) => {
        if (!getSelectedCheckboxes(form).length) {
          event.preventDefault()
          return
        }
        const confirmMessage = button.dataset.confirmMessage
        if (confirmMessage && !window.confirm(confirmMessage)) {
          event.preventDefault()
        }
      })
    })

    form.addEventListener('submit', (event) => {
      const submitter = event.submitter
      if (!submitter || !submitter.matches(SELECTORS.actionButton)) {
        return
      }
      if (!getSelectedCheckboxes(form).length) {
        event.preventDefault()
        updateBatchActions(form)
      }
    })

    updateBatchActions(form)
  })
}

onReady(() => {
  initFeedbackBulkActions()
})

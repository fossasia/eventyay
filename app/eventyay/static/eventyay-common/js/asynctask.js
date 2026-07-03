/**
 * Async task handler for orga pages.
 * Intercepts forms with [data-asynctask] and shows a loading overlay
 * while polling for task completion, matching the tickets import UI.
 */

let taskId = null
let checkUrl = null
let pollTimeout = null
let isLong = false
let isSubmitting = false

const modal = () => document.getElementById('loadingmodal')

const show = (headline) => {
    const el = modal()
    if (!el) return
    const h3 = el.querySelector('h3')
    if (h3) h3.textContent = headline
    const progress = el.querySelector('.progress')
    if (progress) progress.style.display = 'none'
    document.body.classList.add('loading')
}

const hide = () => {
    if (pollTimeout) {
        clearTimeout(pollTimeout)
        pollTimeout = null
    }
    taskId = null
    checkUrl = null
    isSubmitting = false
    document.body.classList.remove('loading')
}

const setStatus = (text) => {
    const el = modal()
    if (!el) return
    const p = el.querySelector('p.status')
    if (p) p.textContent = text
}

const setProgress = (pct) => {
    const el = modal()
    if (!el) return
    const progress = el.querySelector('.progress')
    const bar = el.querySelector('.progress-bar')
    if (progress) progress.style.display = ''
    if (bar) bar.style.width = pct + '%'
}

const poll = () => {
    fetch(checkUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(r => {
            if (!r.ok) {
                throw new Error('Network response was not ok')
            }
            return r.json()
        })
        .then(data => {
            if (data.ready && data.redirect) {
                hide()
                location.href = data.redirect
                return
            }
            if (typeof data.percentage === 'number') {
                setProgress(data.percentage)
            }
            if (isLong) {
                if (data.started) {
                    setStatus(gettext('Your request is currently being processed. Depending on the size of your event, this might take up to a few minutes.'))
                } else {
                    setStatus(gettext('Your request has been queued on the server and will soon be processed.'))
                }
            }
            pollTimeout = setTimeout(poll, 250)
        })
        .catch(() => {
            pollTimeout = setTimeout(poll, 5000)
        })
}

const submit = (form) => {
    if (isSubmitting) return
    isSubmitting = true

    const headline = form.dataset.asynctaskHeadline || gettext('We are processing your request …')
    isLong = form.hasAttribute('data-asynctask-long')
    show(headline)
    setStatus(gettext('We are currently sending your request to the server.'))

    const body = new URLSearchParams(new FormData(form))
    body.append('ajax', '1')

    fetch(form.action || location.href, {
        method: 'POST',
        body,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
        .then(async r => {
            const contentType = r.headers.get('content-type')
            if (contentType && contentType.includes('text/html')) {
                const html = await r.text()
                document.open()
                document.write(html)
                document.close()
                return null
            }
            if (!r.ok) {
                throw new Error('Network response was not ok')
            }
            return r.json()
        })
        .then(data => {
            if (!data) return
            if (data.redirect) {
                hide()
                location.href = data.redirect
                return
            }
            if (!data.check_url) {
                throw new Error('check_url missing')
            }
            taskId = data.async_id
            checkUrl = data.check_url
            if (isLong && data.started) {
                setStatus(gettext('Your request is currently being processed. Depending on the size of your event, this might take up to a few minutes.'))
            }
            pollTimeout = setTimeout(poll, 100)
        })
        .catch(() => {
            hide()
            alert(gettext('An error occurred. Please try again.'))
        })
}

const init = () => {
    document.addEventListener('submit', (e) => {
        const form = e.target.closest('form[data-asynctask]')
        if (!form) return
        e.preventDefault()
        submit(form)
    })
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init)
} else {
    init()
}

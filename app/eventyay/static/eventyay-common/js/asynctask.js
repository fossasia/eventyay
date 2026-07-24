/**
 * Import-specific async task handler.
 * Intercepts forms with [data-import-task] and shows a loading overlay
 * with progress bar, minimize button, and session persistence.
 *
 * This script is ONLY for import flows (attendees, speakers, schedule).
 * General async tasks (exports, downloads, etc.) are handled by
 * pretixbase/js/asynctask.js via [data-asynctask].
 */

let taskId = null
let checkUrl = null
let pollTimeout = null
let isLong = false
let isSubmitting = false

const modal = () => {
    let el = document.getElementById('import-loadingmodal')
    if (!el) {
        const original = document.getElementById('loadingmodal')
        if (original) {
            el = original.cloneNode(true)
            el.id = 'import-loadingmodal'
            document.body.appendChild(el)
        }
    }
    return el
}

const show = (headline) => {
    const el = modal()
    if (!el) return
    const h3 = el.querySelector('h3')
    if (h3) h3.textContent = headline
    const progress = el.querySelector('.progress')
    if (progress) progress.style.display = ''
    const bar = el.querySelector('.progress-bar')
    if (bar) {
        bar.style.width = '0%'
        bar.classList.add('progress-bar-striped', 'active')
    }
    const minimizeBtn = el.querySelector('.loadingmodal-minimize')
    if (minimizeBtn) minimizeBtn.style.display = ''
    document.body.classList.remove('import-loading-minimized')
    document.body.classList.add('import-loading')
    document.body.classList.add('is-import-task')
}

const hide = () => {
    if (pollTimeout) {
        clearTimeout(pollTimeout)
        pollTimeout = null
    }
    taskId = null
    checkUrl = null
    isSubmitting = false
    document.body.classList.remove('import-loading')
    document.body.classList.remove('import-loading-minimized')
    document.body.classList.remove('is-import-task')
    sessionStorage.removeItem('eventyay_async_task_import')
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
    if (bar) {
        bar.classList.remove('progress-bar-striped', 'active')
        bar.style.width = pct + '%'
    }
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
            if (data.ready) {
                const bar = document.querySelector('#import-loadingmodal .progress-bar')
                const btnIcon = document.querySelector('#import-loadingmodal .loadingmodal-minimize i')
                const h3 = document.querySelector('#import-loadingmodal h3')
                const bigIcon = document.querySelector('#import-loadingmodal .big-rotating-icon')

                if (bar) {
                    bar.classList.remove('progress-bar-striped', 'active')
                    bar.style.width = '100%'
                }
                
                if (data.success || typeof data.success === 'undefined') {
                    if (bar) bar.classList.add('bg-success', 'progress-bar-success')
                    if (btnIcon) btnIcon.className = 'fa fa-check'
                    if (h3) h3.textContent = gettext('Task completed')
                    if (bigIcon) {
                        bigIcon.className = 'fa fa-check big-rotating-icon'
                        bigIcon.style.animation = 'none'
                        bigIcon.style.color = '#5cb85c'
                    }
                } else {
                    if (bar) bar.classList.add('bg-danger', 'progress-bar-danger')
                    if (btnIcon) btnIcon.className = 'fa fa-times'
                    if (h3) h3.textContent = data.message || gettext('Task failed')
                    if (bigIcon) {
                        bigIcon.className = 'fa fa-times big-rotating-icon'
                        bigIcon.style.animation = 'none'
                        bigIcon.style.color = '#d9534f'
                    }
                }

                sessionStorage.removeItem('eventyay_async_task_import')

                setTimeout(() => {
                    hide()
                }, 2000)
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

    const headline = form.dataset.importTaskHeadline || gettext('We are processing your request …')
    isLong = form.hasAttribute('data-import-task-long')
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
                const newDoc = new DOMParser().parseFromString(html, 'text/html')
                const newWrapper = newDoc.querySelector('#page-wrapper')
                const oldWrapper = document.querySelector('#page-wrapper')
                if (newWrapper && oldWrapper) {
                    oldWrapper.replaceWith(newWrapper)
                } else {
                    document.documentElement.replaceWith(newDoc.documentElement)
                }
                hide()
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

            sessionStorage.setItem('eventyay_async_task_import', JSON.stringify({
                id: taskId,
                checkUrl: checkUrl,
                isLong: isLong,
                headline: document.querySelector('#import-loadingmodal h3') ? document.querySelector('#import-loadingmodal h3').textContent : '',
                minimized: document.body.classList.contains('import-loading-minimized'),
                path: location.pathname
            }))

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
    const importForms = document.querySelectorAll('form[data-import-task]')
    const storedTask = sessionStorage.getItem('eventyay_async_task_import')
    if (importForms.length > 0 || storedTask) {
        const content = document.querySelector('#loadingmodal .modal-card-content')
        if (content && !content.querySelector('.loadingmodal-minimize')) {
            const div = document.createElement('div')
            div.className = 'pull-right'
            const btn = document.createElement('button')
            btn.type = 'button'
            btn.className = 'btn btn-default btn-xs loadingmodal-minimize'
            btn.title = gettext('Minimize')
            const icon = document.createElement('i')
            icon.className = 'fa fa-window-minimize'
            btn.appendChild(icon)
            div.appendChild(btn)
            content.insertBefore(div, content.firstChild)
        }
    }

    document.addEventListener('submit', (e) => {
        const form = e.target.closest('form[data-import-task]')
        if (!form) return
        e.preventDefault()
        submit(form)
    })

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.loadingmodal-minimize')
        if (!btn) return
        e.preventDefault()
        document.body.classList.toggle('import-loading-minimized')

        const storedTask = sessionStorage.getItem('eventyay_async_task_import')
        if (storedTask) {
            try {
                const task = JSON.parse(storedTask)
                task.minimized = document.body.classList.contains('import-loading-minimized')
                sessionStorage.setItem('eventyay_async_task_import', JSON.stringify(task))
            } catch (err) {}
        }
    })

    if (storedTask) {
        try {
            const task = JSON.parse(storedTask)
            taskId = task.id
            checkUrl = task.checkUrl
            isLong = task.isLong

            show(task.headline || gettext('We are processing your request …'))
            
            // Auto-minimize if we navigated to a different page while task is running
            // to avoid blocking non-import pages (e.g. export tickets)
            if (task.minimized || task.path !== location.pathname) {
                document.body.classList.add('import-loading-minimized')
                if (!task.minimized) {
                    task.minimized = true
                    task.path = location.pathname
                    sessionStorage.setItem('eventyay_async_task_import', JSON.stringify(task))
                }
            }

            pollTimeout = setTimeout(poll, 100)
        } catch (e) {
            sessionStorage.removeItem('eventyay_async_task_import')
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init)
} else {
    init()
}

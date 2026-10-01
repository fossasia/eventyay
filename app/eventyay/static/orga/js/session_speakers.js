const form = document.getElementById('session-speaker-form')

if (form) {
    const errors = document.getElementById('session-speaker-errors')
    const status = document.getElementById('session-speaker-status')
    const button = form.querySelector('button[type="submit"]')
    let submitting = false

    const showErrors = (messages) => {
        const list = document.createElement('ul')
        for (const message of messages) {
            const item = document.createElement('li')
            item.textContent = message
            list.append(item)
        }
        errors.replaceChildren(list)
        errors.classList.remove('d-none')
        errors.focus()
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault()
        if (submitting) return
        submitting = true
        button.disabled = true
        form.setAttribute('aria-busy', 'true')
        errors.classList.add('d-none')
        status.textContent = ''

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                credentials: 'same-origin',
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                },
            })
            if (response.status === 400 && response.headers.get('content-type')?.includes('application/json')) {
                const data = await response.json()
                showErrors(data.errors.flatMap(({ label, messages }) =>
                    messages.map((message) => label ? `${label}: ${message}` : message)))
                return
            }
            if (!response.ok || response.redirected) {
                console.error('Could not add session speaker', response.status)
                showErrors([form.dataset.errorMessage])
                return
            }
            const data = await response.json()
            document.getElementById('session-speaker-list').innerHTML = data.speakers
            const names = document.getElementById('submission-speaker-names')
            names.innerHTML = data.speaker_names
            names.prepend(document.createTextNode(' – '))
            const locale = form.elements.namedItem('locale')
            const invitationLocale = locale?.value
            form.reset()
            if (locale) locale.value = invitationLocale
            form.querySelectorAll('.invalid-feedback, .errorlist').forEach((element) => element.remove())
            form.dispatchEvent(new Event('speaker-added'))
            for (const textarea of form.querySelectorAll('textarea[data-tiptap-profile]')) {
                textarea.__eventyayTiptapEditor?.commands.clearContent()
            }
            status.textContent = data.message
            document.getElementById(`session-speaker-${data.speaker_code}`)?.focus()
        } catch (error) {
            console.error('Could not add session speaker', error)
            showErrors([form.dataset.errorMessage])
        } finally {
            submitting = false
            button.disabled = false
            form.removeAttribute('aria-busy')
        }
    })
}

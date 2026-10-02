const initUserSearch = () => {
    const remoteURL = document.getElementById("vars").getAttribute("remoteUrl")
    let select = document.querySelector("#id_email")
    if (!select) select = document.querySelector("#id_invite-email")
    if (!select) select = document.querySelector("#id_speaker-email")
    if (!select) return

    const usersByEmail = new Map()
    const toChoice = (user) => ({
        value: user.email,
        label: user.label,
        customProperties: {
            name: user.name,
        },
    })
    const fetchUsers = async (search) => {
        const url = new URL(remoteURL, window.location.origin)
        url.searchParams.set("search", search)
        const response = await fetch(url)
        if (!response.ok) throw new Error(`Speaker search failed with status ${response.status}`)
        const data = await response.json()
        const users = data.results.filter((user) => user.email)
        users.forEach((user) => usersByEmail.set(user.email.toLowerCase(), user))
        return users
    }

    const choices = new Choices(select, {
        maxItemCount: 1,
        singleModeForMultiSelect: true,
        closeDropdownOnSelect: true,
        addChoices: true,
        removeItems: true,
        removeItemButton: true,
        removeItemButtonAlignLeft: true,
        searchEnabled: true,
        searchFloor: 3,
        searchResultLimit: -1,
        placeholder: true,
        placeholderValue: select.getAttribute("placeholder"),
        itemSelectText: "",
        noResultsText: "",
        noChoicesText: "",
        addItemText: "",
        removeItemLabelText: "×",
        removeItemIconText: "×",
        maxItemText: "",
    })
    select.form?.addEventListener("speaker-added", () => {
        choices.removeActiveItems()
        choices.clearInput()
    })
    select.addEventListener("search", (ev) => {
        fetchUsers(ev.detail.value)
            .then((users) => {
                choices.setChoices(
                    users.map(toChoice),
                    "value",
                    "label",
                    true,
                )
            })
            .catch((error) => console.error("Could not load speaker autocomplete results", error))
    })
    select.addEventListener("addItem", (ev) => {
        if (ev.detail.customProperties && ev.detail.customProperties.name) {
            let nameInput = document.querySelector("#id_name")
            if (!nameInput) nameInput = document.querySelector("#id_speaker")
            if (!nameInput) nameInput = document.querySelector("#id_speaker-name")
            if (!nameInput || nameInput.value.length) return
            nameInput.value = ev.detail.customProperties.name
        }
    })
    select.parentElement.parentElement
        .querySelector("input")
        .addEventListener("blur", async (ev) => {
            const unfinishedInput = ev.target.value.trim()
            if (!unfinishedInput) return
            if (select.value != unfinishedInput) {
                let existingUser = usersByEmail.get(unfinishedInput.toLowerCase())
                if (!existingUser) {
                    try {
                        await fetchUsers(unfinishedInput)
                        existingUser = usersByEmail.get(unfinishedInput.toLowerCase())
                    } catch (error) {
                        console.error("Could not match the entered speaker email", error)
                    }
                }
                if (existingUser) {
                    choices.setChoices([toChoice(existingUser)])
                    choices.setChoiceByValue(existingUser.email)
                } else {
                    choices.setChoices([
                        {
                            value: unfinishedInput,
                            label: unfinishedInput,
                            selected: true,
                        },
                    ])
                }
                ev.target.value = ""
            }
        })
}
initUserSearch()

const initSessionSpeakers = () => {
    const form = document.getElementById('session-speaker-form')
    if (!form) return
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
            const page = DOMPurify.sanitize(data.html, { RETURN_DOM_FRAGMENT: true })
            document.getElementById('session-speaker-list').replaceChildren(
                ...page.querySelector('#session-speaker-list').childNodes)
            document.getElementById('submission-speaker-names').replaceChildren(
                ...page.querySelector('#submission-speaker-names').childNodes)
            const locale = form.elements.namedItem('locale')
            const invitationLocale = locale?.value
            form.reset()
            if (locale) locale.value = invitationLocale
            form.querySelectorAll('.invalid-feedback, .errorlist').forEach((element) => element.remove())
            form.dispatchEvent(new Event('speaker-added'))
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
initSessionSpeakers()

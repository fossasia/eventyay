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
    let nameInput = document.querySelector("#id_name")
    if (!nameInput) nameInput = document.querySelector("#id_speaker")
    if (!nameInput) nameInput = document.querySelector("#id_speaker-name")
    // The name we filled in from the selected user. Anything the organizer
    // types themselves is left alone.
    let autoFilledName = null
    const nameIsAutoFilled = () => nameInput && autoFilledName !== null && nameInput.value === autoFilledName
    if (nameInput) {
        nameInput.addEventListener("input", () => {
            autoFilledName = null
        })
    }
    select.addEventListener("addItem", (ev) => {
        if (!nameInput) return
        if (nameInput.value.length && !nameIsAutoFilled()) return
        const name = ev.detail.customProperties?.name || ""
        nameInput.value = name
        autoFilledName = name || null
    })
    select.addEventListener("removeItem", () => {
        if (!nameIsAutoFilled()) return
        nameInput.value = ""
        autoFilledName = null
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

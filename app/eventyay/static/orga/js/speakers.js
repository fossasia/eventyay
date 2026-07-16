const initUserSearch = () => {
    const remoteURL = document.getElementById("vars").getAttribute("remoteUrl")
    let select = document.querySelector("#id_email")
    if (!select) select = document.querySelector("#id_invite-email")
    if (!select) select = document.querySelector("#id_speaker-email")
    if (!select) return

    const usersByEmail = new Map()
    const toChoice = (user) => ({
        value: user.email,
        label: `${user.name} <${user.email}>`,
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

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
            biography: user.biography,
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
        if (ev.detail.customProperties) {
            let nameInput = document.querySelector("#id_name")
            if (!nameInput) nameInput = document.querySelector("#id_speaker")
            if (!nameInput) nameInput = document.querySelector("#id_speaker-name")
            if (nameInput && 'name' in ev.detail.customProperties) {
                nameInput.value = ev.detail.customProperties.name || ''
            }
            
            let bioInput = document.querySelector("#id_speaker-biography")
            if (bioInput && 'biography' in ev.detail.customProperties) {
                const bioValue = ev.detail.customProperties.biography || ''
                bioInput.value = bioValue
                if (bioInput.__eventyayTiptapEditor) {
                    bioInput.__eventyayTiptapEditor.commands.setContent(bioValue);
                }
            }
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

const initSpeakerModeToggle = () => {
    const radioInputs = document.querySelectorAll('input[name="speaker-speaker_action"]');
    if (!radioInputs.length) return;

    const emailField = document.querySelector('#id_speaker-email');
    const nameField = document.querySelector('#id_speaker-name');
    const biographyField = document.querySelector('#id_speaker-biography');
    const localeField = document.querySelector('#id_speaker-locale');

    const toggleRequired = (inputNode, isRequired) => {
        if (!inputNode) return;
        const formGroup = inputNode.closest('.form-group');
        if (!formGroup) return;
        
        const starSpan = formGroup.querySelector('label span.d-inline.text-danger');
        if (starSpan) {
            starSpan.textContent = isRequired ? ' *' : '';
        }
        
        const optSpan = formGroup.querySelector('label span.optional');
        if (isRequired) {
            if (optSpan) optSpan.style.display = 'none';
            inputNode.setAttribute('required', 'required');
        } else {
            if (optSpan) optSpan.style.display = 'inline';
            inputNode.removeAttribute('required');
        }
    };

    const toggleVisibility = (inputNode, isVisible) => {
        if (!inputNode) return;
        const formGroup = inputNode.closest('.form-group');
        if (!formGroup) return;
        if (isVisible) {
            formGroup.classList.remove('d-none');
        } else {
            formGroup.classList.add('d-none');
        }
    };

    // Hide the "Optional" label for the radio button group itself
    if (radioInputs.length > 0) {
        const actionFormGroup = radioInputs[0].closest('.form-group');
        if (actionFormGroup) {
            const optSpan = actionFormGroup.querySelector('label span.optional');
            if (optSpan) optSpan.style.display = 'none';
        }
    }

    const updateSpeakerMode = () => {
        let selectedAction = 'none';
        for (const radio of radioInputs) {
            if (radio.checked) {
                selectedAction = radio.value;
                break;
            }
        }

        if (selectedAction === 'none') {
            toggleVisibility(emailField, false);
            toggleVisibility(nameField, false);
            toggleVisibility(biographyField, false);
            toggleVisibility(localeField, false);
            toggleRequired(emailField, false);
            toggleRequired(nameField, false);
            toggleRequired(biographyField, false);
        } else if (selectedAction === 'add') {
            toggleVisibility(emailField, true);
            toggleVisibility(nameField, true);
            toggleVisibility(biographyField, true);
            toggleVisibility(localeField, true);
            
            toggleRequired(emailField, false);
            toggleRequired(nameField, nameField && nameField.getAttribute('data-required') === 'true');
            toggleRequired(biographyField, biographyField && biographyField.getAttribute('data-required') === 'true');
        }
    };

    for (const radio of radioInputs) {
        radio.addEventListener('change', updateSpeakerMode);
    }
    updateSpeakerMode();
};

document.addEventListener('DOMContentLoaded', initSpeakerModeToggle);
// Also run immediately in case DOMContentLoaded already fired or for dynamically loaded forms
initSpeakerModeToggle();

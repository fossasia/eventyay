const addSession = document.getElementById("id_add_session")
const linkSession = document.getElementById("id_link_existing_session")
const sessionSection = document.getElementById("session_section")
const existingSessionSection = document.getElementById("existing_session_section")

const toggleSection = (section, visible) => {
    if (!section) return
    section.classList.toggle("d-none", !visible)
    section.querySelectorAll("input, select, textarea").forEach((field) => {
        field.disabled = !visible
    })
}

const applySessionSections = () => {
    toggleSection(sessionSection, addSession?.checked)
    toggleSection(existingSessionSection, linkSession?.checked)
}

addSession?.addEventListener("change", () => {
    if (addSession.checked && linkSession) linkSession.checked = false
    applySessionSections()
})

linkSession?.addEventListener("change", () => {
    if (linkSession.checked && addSession) addSession.checked = false
    applySessionSections()
})

applySessionSections()

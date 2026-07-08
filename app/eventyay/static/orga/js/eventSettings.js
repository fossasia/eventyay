const dateHelpText = document.getElementById("id_date_to_helptext")

const showDateHelpText = () => {
    dateHelpText.classList.remove("d-none")
}

function updateSessionPopularitySubfields({ defaultChildOnEnable = false } = {}) {
    const parent = document.getElementById("id_session_popularity_enabled")
    const child = document.getElementById("id_session_popularity_show_on_schedule")
    const wrapper = document.getElementById("session-popularity-subfields")
    if (!parent || !child || !wrapper) return

    const enabled = parent.checked
    child.disabled = !enabled
    wrapper.classList.toggle("subfield-disabled", !enabled)
    if (!enabled) {
        child.checked = false
    } else if (defaultChildOnEnable) {
        child.checked = true
    }
}

onReady(() => {
    if (dateHelpText) {
        dateHelpText.classList.add("d-none")
        document.getElementById("id_date_to")?.addEventListener("change", showDateHelpText)
        document.getElementById("id_date_from")?.addEventListener("change", showDateHelpText)
    }

    updateSessionPopularitySubfields()
    document.getElementById("id_session_popularity_enabled")?.addEventListener("change", () => {
        updateSessionPopularitySubfields({ defaultChildOnEnable: true })
    })
})

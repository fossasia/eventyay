/* Switches the Delivery section between sending immediately and scheduling,
 * keeping the scheduled time inputs hidden and empty unless they apply. */

const setDeliveryMode = (schedule, scheduled) => {
    schedule.hidden = !scheduled
    if (!scheduled) {
        schedule.querySelectorAll("input").forEach((input) => {
            input.value = ""
        })
    }
}

const initDeliveryMode = () => {
    const schedule = document.querySelector("#delivery-schedule")
    const now = document.querySelector("#delivery-mode-now")
    const later = document.querySelector("#delivery-mode-later")
    if (!schedule || !now || !later) return

    const hasValue = [...schedule.querySelectorAll("input")].some((input) => input.value)
    if (hasValue) {
        later.checked = true
    }
    setDeliveryMode(schedule, later.checked)

    now.addEventListener("change", () => setDeliveryMode(schedule, false))
    later.addEventListener("change", () => setDeliveryMode(schedule, true))
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDeliveryMode)
} else {
    initDeliveryMode()
}

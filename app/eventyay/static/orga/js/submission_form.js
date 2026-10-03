const updateVisibility = () => {
    const stateEl = document.querySelector("#show-if-state")
    if (!stateEl) return
    if (
        ["accepted", "confirmed"].includes(
            document.querySelector("#id_state").value,
        )
    ) {
        stateEl.classList.remove("d-none")
    } else {
        stateEl.classList.add("d-none")
    }
}

if (document.querySelector("#id_state")) {
    document
        .querySelector("#id_state")
        .addEventListener("change", updateVisibility)
    updateVisibility()
}

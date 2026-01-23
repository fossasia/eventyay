const changeSelectAll = () => {
    const selectAllCheckbox = document.querySelector("#select-all")
    if (!selectAllCheckbox) return

    const fieldset = selectAllCheckbox.closest("fieldset")
    if (!fieldset) return

    fieldset.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
        if (checkbox.id === "select-all") return
        checkbox.checked = selectAllCheckbox.checked
    })
}

const addHook = () => {
    const updateVisibility = () => {
        const delimiter = document.querySelector("#data-delimiter")
        if (delimiter) {
            const csvRadio = document.querySelector("#id_export_format input[value='csv']")
            delimiter.style.display = csvRadio?.checked ? "block" : "none"
        }
    }

    updateVisibility()
    document.querySelectorAll("#id_export_format input").forEach((element) =>
        element.addEventListener("change", updateVisibility)
    )

    const selectAll = document.querySelector("#select-all")
    if (selectAll) {
        selectAll.addEventListener("change", changeSelectAll)
    }
}

onReady(addHook)

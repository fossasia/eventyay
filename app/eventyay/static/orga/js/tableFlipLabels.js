function normalizeTableHeaderLabel(header) {
    return header.textContent.replace(/\s+/g, " ").trim()
}

function applyTableFlipLabels(root = document) {
    if (!window.matchMedia("(max-width: 768px)").matches) {
        return
    }

    root.querySelectorAll("table.table-flip").forEach((table) => {
        const headers = Array.from(table.querySelectorAll("thead th")).map(
            normalizeTableHeaderLabel,
        )

        table.querySelectorAll("tbody tr").forEach((row) => {
            const headerOffset = row.querySelector("th") ? 1 : 0
            row.querySelectorAll("td").forEach((cell, index) => {
                const label = headers[index + headerOffset] || ""
                if (label) {
                    cell.dataset.label = label
                } else {
                    delete cell.dataset.label
                }
            })
        })
    })
}

onReady(() => {
    applyTableFlipLabels()
})

document.addEventListener("eventyay:ajax-results-replaced", (event) => {
    applyTableFlipLabels(event.detail?.container ?? document)
})

window.addEventListener("resize", () => {
    applyTableFlipLabels()
})

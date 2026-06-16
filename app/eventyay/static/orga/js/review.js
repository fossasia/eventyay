/*
 * RANGE SLIDER
 */
const slider = document.querySelector("#review-count")

if (slider) {
    const max = parseInt(slider.dataset.max)
    let params =
        new URLSearchParams(window.location.search).get("review-count") || ","
    params = params.split(",")

    const minInitial = params ? params[0] : 0
    const maxInitial = params ? params[1] : max

    const reviewSlider = new rSlider({
        target: "#review-count",
        values: Array(max + 1)
            .fill()
            .map((element, index) => index),
        range: true,
        tooltip: false,
        scale: true,
        labels: true,
        width: "270px",
        set: [parseInt(minInitial), parseInt(maxInitial)],
    })
}

/*
 * COLUMN SELECTION
 */
const updateColumnVisibility = (ev) => {
    if (ev.target.checked) {
        document
            .querySelectorAll(`.${ev.target.id}`)
            .forEach((e) => e.classList.remove("d-none"))
    } else {
        document
            .querySelectorAll(`.${ev.target.id}`)
            .forEach((e) => e.classList.add("d-none"))
    }
}

// Re-apply the chosen columns to a freshly swapped-in table.
const applyColumnVisibility = () => {
    document
        .querySelectorAll("#column-select input[type=checkbox]")
        .forEach((checkbox) => {
            document
                .querySelectorAll(`.${checkbox.id}`)
                .forEach((e) => e.classList.toggle("d-none", !checkbox.checked))
        })
}

document
    .querySelectorAll("#column-select input[type=checkbox]")
    .forEach((element) =>
        element.addEventListener("change", updateColumnVisibility),
    )

/*
 * REVIEW SELECTION
 *
 * When a radio button is selected (or has been selected from the start):
 * add the active class to its unmark-radio element
 * Count both classes of radio buttons and update counters
 * When .unmark-radio is clicked, deactivate its neighbored labels and update count
 *
 * Bound inside a function so it can re-run after an in-place AJAX sort/filter
 * replaces the table and submit bar.
 */
const initReviewSelection = () => {
    const submitBar = document.querySelector("#submitBar")
    if (!submitBar) return

    const count = { accept: 0, reject: 0 }
    const acceptLabel = document.querySelector("#acceptCount")
    const rejectLabel = document.querySelector("#rejectCount")

    const updateCount = () => {
        count.accept = 0
        count.reject = 0
        document
            .querySelectorAll(".review-table tbody .reject input[type=radio]")
            .forEach((element) => {
                if (element.checked) {
                    count.reject += 1
                    element.parentElement.parentElement
                        .querySelector(".unmark-radio")
                        .classList.add("active")
                }
            })
        document
            .querySelectorAll(".review-table tbody .accept input[type=radio]")
            .forEach((element) => {
                if (element.checked) {
                    count.accept += 1
                    element.parentElement.parentElement
                        .querySelector(".unmark-radio")
                        .classList.add("active")
                }
            })
        if (!(count.accept || count.reject)) {
            submitBar.classList.add("d-none")
        } else {
            submitBar.classList.remove("d-none")
        }
        if (acceptLabel.firstChild) acceptLabel.removeChild(acceptLabel.firstChild)
        acceptLabel.appendChild(document.createTextNode(count.accept))
        if (rejectLabel.firstChild) rejectLabel.removeChild(rejectLabel.firstChild)
        rejectLabel.appendChild(document.createTextNode(count.reject))
    }

    document
        .querySelectorAll(".review-table tbody .radio input[type=radio]")
        .forEach((element) => {
            element.addEventListener("click", () => {
                updateCount()
            })
        })

    document
        .querySelectorAll(".review-table tbody .unmark-radio")
        .forEach((element) => {
            element.addEventListener("click", (ev) => {
                ev.target.parentElement.parentElement
                    .querySelectorAll("input[type=radio]")
                    .forEach((rad) => {
                        rad.checked = false
                    })
                ev.target.parentElement.classList.remove("active")
                updateCount()
            })
        })

    const submitText = document.querySelector("#submitText")
    if (submitText) submitText.classList.remove("d-none")

    const acceptAll = document.getElementById("a-all")
    if (acceptAll) {
        acceptAll.addEventListener("click", (ev) => {
            document.querySelectorAll("tbody .action-row").forEach((td) => {
                if (
                    td.querySelector(".radio.reject input") &&
                    !td.querySelector(".radio.reject input").checked
                ) {
                    td.querySelector(".radio.accept input").checked = true
                }
            })
            updateCount()
        })
    }

    const rejectAll = document.getElementById("r-all")
    if (rejectAll) {
        rejectAll.addEventListener("click", (ev) => {
            document.querySelectorAll("tbody .action-row").forEach((td) => {
                if (
                    td.querySelector(".radio.accept input") &&
                    !td.querySelector(".radio.accept input").checked
                ) {
                    td.querySelector(".radio.reject input").checked = true
                }
            })
            updateCount()
        })
    }

    const clearAll = document.getElementById("u-all")
    if (clearAll) {
        clearAll.addEventListener("click", (ev) => {
            document.querySelectorAll("input[type=radio]").forEach((rad) => {
                rad.checked = false
            })
            ev.target.parentElement.classList.remove("active")
            updateCount()
        })
    }

    updateCount()
}

initReviewSelection()

document.addEventListener("eventyay:ajax-results-replaced", () => {
    initReviewSelection()
    applyColumnVisibility()
})

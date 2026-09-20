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

/*
 * INLINE REVIEW SCORE
 */
const initReviewScore = () => {
    document
        .querySelectorAll(".review-score-select")
        .forEach((element) => {
            if (element.dataset.reviewScoreInitialized) {
                return
            }
            element.dataset.reviewScoreInitialized = "true"
            element.addEventListener("change", async (ev) => {
                const select = ev.target
                const previousValue = select.dataset.previousValue

                const statusWrapper = select.closest("td")
                const errorEl = statusWrapper.querySelector(".review-score-error")
                const resetStatus = () => {
                    statusWrapper.querySelectorAll("i.working, i.done, i.fail").forEach((icon) => {
                        icon.classList.add("d-none")
                    })
                }
                const setStatus = (statusName) => {
                    const statusIcon = statusWrapper.querySelector("." + statusName)
                    if (!statusIcon) {
                        return
                    }
                    resetStatus()
                    statusIcon.classList.remove("d-none")
                    if (statusWrapper.resetTimeout) {
                        clearTimeout(statusWrapper.resetTimeout)
                    }
                    statusWrapper.resetTimeout = setTimeout(resetStatus, 3000)
                }
                if (errorEl) {
                    errorEl.textContent = ""
                    errorEl.classList.add("d-none")
                }
                setStatus("working")
                try {
                    select.disabled = true
                    const csrfToken = getCookie("eventyay_csrftoken")

                    const response = await fetch(select.dataset.url, {
                        method: "POST",
                        headers: {
                            "X-CSRFToken": csrfToken,
                        },
                        body: new URLSearchParams({
                            score: select.value,
                            category: select.value ? select.selectedOptions[0].dataset.category : "",
                        }),
                    })

                    const data = await response.json()

                    if (!response.ok || !data.ok) {
                        throw new Error(data.error)
                    }

                    select.dataset.previousValue = select.value

                    const row = select.closest("tr")
                    const missingReviewsCount = document.querySelector("#missing-reviews-count")
                    if (missingReviewsCount) {
                        if (data.missing_reviews === 0) {
                            document.querySelector("#review-progress-content").textContent = "You’ve got no proposals left to review!"
                        } else {
                            missingReviewsCount.textContent = ngettext(
                                "%s proposal is waiting for your review.",
                                "%s proposals are waiting for your review.",
                                data.missing_reviews
                            ).replace("%s", data.missing_reviews)
                        }
                    }
                    if (row) {
                        const scoreCell = row.querySelector(".review-current-score")
                        const reviewCountCell = row.querySelector(".review-count-value")
                        if (scoreCell) {
                            scoreCell.textContent = data.aggregate == null ? "-" : Number(data.aggregate).toString()
                        }

                        if (reviewCountCell) {
                            reviewCountCell.textContent = data.reviews ?? "-"
                        }
                        const reviewTotalCount = row.querySelector(".review-total-count")
                        if (reviewTotalCount) {
                            reviewTotalCount.textContent = data.review_count ?? "-"
                        }
                        const reviewCompleted = row.querySelector(".review-completed")
                        if (reviewCompleted) {
                            reviewCompleted.classList.toggle("d-none", !select.value)
                        }
                    }
                    setStatus("done")
                } catch (error) {
                    select.value = previousValue
                    if (errorEl) {
                        errorEl.textContent = error.message || "Could not save review score. Please try again."
                        errorEl.classList.remove("d-none")
                    }
                    setStatus("fail")
                } finally {
                    select.disabled = false
                }
            })

            element.dataset.previousValue = element.value
        })
}

initReviewScore()

document.addEventListener("eventyay:ajax-results-replaced", () => {
    initReviewScore()
})

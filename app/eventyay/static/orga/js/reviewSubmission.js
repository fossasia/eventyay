document.body.addEventListener("keydown", function (e) {
    if (!(e.keyCode == 13 && (e.metaKey || e.ctrlKey))) return

    if (e.target.form) {
        e.target.form.submit()
    }
})

// Use event delegation for edit buttons to handle multiple reviews
document.body.addEventListener("click", function (e) {
    if (e.target.classList.contains("edit-review")) {
        const ownReviewSection = document.querySelector("#own-review")
        if (ownReviewSection) {
            ownReviewSection.classList.remove("d-none")
        }
    }
})

document.querySelectorAll(".hide-optional").forEach((element) => {
    while (
        !element.classList.contains("form-group") &&
        element.nodeName !== "BODY"
    ) {
        element = element.parentElement
    }
    if (element.nodeName === "BODY") return
    element.querySelector(".optional").classList.add("d-none")
})

const titleParts = document.title.split("::")

const updateTitle = (newTitle) => {
    if (newTitle === "") {
        document.title = titleParts.join("::")
    } else {
        document.title = `${newTitle} ::${titleParts[1]}::${titleParts[2]}`
    }
}

const checkForTitle = () => {
    const titleInput = document.getElementById("id_title")
    if (titleInput) {
        updateTitle(titleInput.value)
    }
}

if (titleParts.length !== 3) {
    console.error(
        "Could not parse site title while adding proposal title change listener."
    )
} else {
    onReady(checkForTitle)
    const titleInput = document.getElementById("id_title")
    if (titleInput) {
        titleInput.addEventListener("change", (ev) => { updateTitle(ev.target.value) })
    }
}

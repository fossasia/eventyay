const initNavSearch = () => {
    const wrapper = document.querySelector("#nav-search-wrapper")
    const summary = wrapper.querySelector(".summary-div")
    const searchInput = wrapper.querySelector("input")
    const searchWrapper = wrapper.querySelector("#nav-search-input-wrapper")
    const apiURL = searchWrapper.getAttribute("data-source")
    const queryStr = "?" + (typeof searchWrapper.getAttribute("data-organiser") !== "undefined" ? "&organiser=" + searchWrapper.getAttribute("data-organiser") : "") + "&query="

    let loadIndicatorTimeout = null
    const showLoadIndicator = () => {
        searchWrapper.querySelector("ul").innerHTML = '<li class="loading"><span class="fa fa-4x fa-cog fa-spin"></span></li>'
    }

    let lastQuery = null
    const triggerSearch = () => {
        if (searchInput.value === lastQuery) {
            return
        }
        searchInput.classList.remove("no-focus")

        const thisQuery = searchInput.value
        lastQuery = thisQuery
        if (loadIndicatorTimeout) clearTimeout(loadIndicatorTimeout)
        loadIndicatorTimeout = setTimeout(showLoadIndicator, 80)

        fetch(apiURL + queryStr + encodeURIComponent(searchInput.value)).then((response) => {
            if (thisQuery !== lastQuery) {
                // Ignore this response, it's for an old query
                return
            }
            if (loadIndicatorTimeout) clearTimeout(loadIndicatorTimeout)

            response.json().then((data) => {
                searchWrapper.querySelectorAll("li").forEach((el) => el.remove())
                data.results.forEach((res) => {
                    const link = document.createElement("a")
                    link.href = res.url
                    const appendText = (className, value, icon) => {
                        const span = document.createElement("span")
                        span.className = className
                        if (icon) {
                            const iconElement = document.createElement("i")
                            iconElement.className = `fa fa-fw ${icon}`
                            span.append(iconElement, " ")
                        }
                        if (className === "search-title" && !icon) {
                            const title = document.createElement("span")
                            title.textContent = value ?? ""
                            span.append(title)
                        } else {
                            span.append(document.createTextNode(value ?? ""))
                        }
                        link.append(span)
                    }
                    if (res.type === "organiser" || res.type === "user") {
                        const icon = res.type === "organiser" ? "fa-users" : "fa-user"
                        appendText("search-title", res.name, icon)
                    } else if (res.type === "user.admin") {
                        appendText("search-title", res.name)
                        appendText("search-detail", res.email, "fa-envelope-o")
                    } else if (res.type === "submission" || res.type === "speaker") {
                        appendText("search-title", res.name)
                        appendText("search-detail", res.event, "fa-calendar")
                    } else if (res.type === "event") {
                        appendText("search-title", res.name)
                        appendText("search-detail", res.organiser, "fa-users")
                        appendText("search-detail", res.date_range, "fa-calendar")
                    }

                    const li = document.createElement("li")
                    li.append(link)
                    searchWrapper.querySelector("ul").append(li)
                }) /* data.results.forEach */
            }) /* response.json().then */
        }) /* fetch.then */
    }

    searchInput.addEventListener("keydown", (ev) => {
        // Keyboard navigation: enter
        if (ev.key === "Enter") {
            const selected = searchWrapper.querySelector("li.active a")
            if (selected) {
                location.href = selected.href
                ev.preventDefault()
                ev.stopPropagation()
            }
        } else if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault()
            ev.stopPropagation()
        }
    })

    searchInput.addEventListener("input", () => {triggerSearch()})

    // Focus search input when dropdown is expanded, and trigger empty search
    wrapper.addEventListener("click", () => {
        triggerSearch()
        setTimeout(() => {
            if (wrapper.getAttribute("open") === "") {
                searchInput.focus()
            } else {
                // Clear search input when dropdown is collapsed
                searchInput.value = ""
            }
        }, 0)
    })

    searchInput.addEventListener("keyup", (ev) => {
        const first = searchWrapper.querySelector("li:not(.query-holder)")
        const last = searchWrapper.querySelector("li:not(.query-holder):last-child")
        const selected = searchWrapper.querySelector("li.active")

        // Keyboard navigation: down
        if (ev.key === "ArrowDown") {
            const next = (selected && selected.nextElementSibling) ? selected.nextElementSibling : first
            if (!next) return
            searchInput.classList.add("no-focus")
            if (selected) { selected.classList.remove("active") }
            next.classList.add("active")
            next.scrollIntoView({ block: 'nearest' })
            ev.preventDefault()
            ev.stopPropagation()
        } else if (ev.key === "ArrowUp") {
            // Keyboard navigation: up
            const prev = (selected && selected.previousElementSibling) ? selected.previousElementSibling : last
            if (!prev || prev.querySelector("input")) return
            searchInput.classList.add("no-focus")
            if (selected) { selected.classList.remove("active") }
            prev.classList.add("active")
            prev.scrollIntoView({ block: 'nearest' })
            ev.preventDefault()
            ev.stopPropagation()
        } else if (ev.key === "Enter") {
            // Keyboard navigation: enter
            ev.preventDefault()
            ev.stopPropagation()
            return true
        }
    })

    // Open search dropdown with alt+k
    document.addEventListener("keydown", (ev) => {
        if (ev.altKey && ev.key === "k") {
            if (summary.open) return
            summary.click()
            ev.preventDefault()
            ev.stopPropagation()
        }
    })
}

onReady(initNavSearch)

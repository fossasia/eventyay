const initNavSearch = () => {
    const wrapper = document.querySelector("#nav-search-wrapper")
    const searchToggle = wrapper.querySelector(".nav-search-toggle")
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
                    let content = ""
                    if (res.type === "organiser" || res.type === "user") {
                        const icon = res.type === "organiser" ? "fa-users" : "fa-user"
                        content = `<span class="search-title"><i class="fa fa-fw ${icon}"></i> ${res.name}</span>`
                    } else if (res.type === "user.admin") {
                        content += `<span class="search-title"><span>${res.name}</span></span>
                            <span class="search-detail"><span class="fa fa-envelope-o fa-fw"></span> ${res.email}</span>`
                    } else if (res.type === "submission" || res.type === "speaker") {
                        content = `<span class="search-title"><span>${res.name}</span></span>
                            <span class="search-detail"><span class="fa fa-calendar fa-fw"></span> ${res.event}</span>`
                    } else if (res.type === "event") {
                        content = `<span class="search-title"><span>${res.name}</span></span>
                            <span class="search-detail"><span class="fa fa-users fa-fw"></span> ${res.organiser}</span>
                            <span class="search-detail"><span class="fa fa-calendar fa-fw"></span> ${res.date_range}</span>`
                    }

                    const li = document.createElement("li")
                    li.innerHTML = `<a href="${res.url}">${content}</a>`
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

    // Toggle search dropdown when search icon is clicked
    const toggleSearchDropdown = () => {
        const isOpen = !searchWrapper.classList.contains("d-none")
        if (isOpen) {
            searchWrapper.classList.add("d-none")
            searchWrapper.setAttribute("aria-hidden", "true")
            if (searchToggle) searchToggle.setAttribute("aria-expanded", "false")
            searchInput.value = ""
            lastQuery = null
        } else {
            searchWrapper.classList.remove("d-none")
            searchWrapper.removeAttribute("aria-hidden")
            if (searchToggle) searchToggle.setAttribute("aria-expanded", "true")
            triggerSearch()
            setTimeout(() => searchInput.focus(), 0)
        }
    }

    const toggleClickTarget = searchToggle || wrapper.querySelector("#nav-search")
    if (toggleClickTarget) {
        toggleClickTarget.addEventListener("click", (ev) => {
            ev.preventDefault()
            ev.stopPropagation()
            toggleSearchDropdown()
        })
    }

    // Close search dropdown when clicking outside
    document.addEventListener("click", (ev) => {
        if (!wrapper.contains(ev.target) && !searchWrapper.classList.contains("d-none")) {
            searchWrapper.classList.add("d-none")
            searchWrapper.setAttribute("aria-hidden", "true")
            if (searchToggle) searchToggle.setAttribute("aria-expanded", "false")
            searchInput.value = ""
            lastQuery = null
        }
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
            ev.preventDefault()
            ev.stopPropagation()
        } else if (ev.key === "ArrowUp") {
            // Keyboard navigation: up
            const prev = (selected && selected.previousElementSibling) ? selected.previousElementSibling : last
            if (!prev || prev.querySelector("input")) return
            searchInput.classList.add("no-focus")
            if (selected) { selected.classList.remove("active") }
            prev.classList.add("active")
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
            if (!searchWrapper.classList.contains("d-none")) return
            toggleSearchDropdown()
            ev.preventDefault()
            ev.stopPropagation()
        }
    })
}

onReady(initNavSearch)

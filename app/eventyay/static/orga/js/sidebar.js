onReady(() => {
    const element = document.querySelector("[data-toggle=sidebar]")
    const sidebar = document.querySelector("aside.sidebar")
    const cls = "sidebar-uncollapsed"
    const isMobile = () => window.matchMedia("(max-width: 768px)").matches

    if (sidebar && localStorage["sidebarVisible"]) {
        sidebar.classList.add(cls)
    }
    if (sidebar && element) {
        element.addEventListener("click", (e) => {
            e.stopPropagation()
            sidebar.classList.toggle(cls)
            localStorage["sidebarVisible"] = sidebar.classList.contains(cls)
                ? "1"
                : ""
        })
    }

    if (sidebar) {
        document.addEventListener("click", (e) => {
            if (!isMobile() || !sidebar.classList.contains(cls)) return
            if (sidebar.contains(e.target) || element?.contains(e.target)) return
            sidebar.classList.remove(cls)
            localStorage["sidebarVisible"] = ""
        })
        sidebar.addEventListener("click", (e) => {
            if (!isMobile()) return
            const link = e.target.closest("a[href]")
            if (link && !link.getAttribute("href").startsWith("#")) {
                sidebar.classList.remove(cls)
                localStorage["sidebarVisible"] = ""
            }
        })
    }
})

const ACTIVE_CLASS_NAMES = ['active', 'underline']
const WIDTH_TOLERANCE = 1

const isVisible = (element) => element.getClientRects().length > 0

const isActive = (element) => ACTIVE_CLASS_NAMES.some((name) => element.classList.contains(name))

const createOverflowNav = (row, bar, overflow) => {
    const menu = overflow.querySelector('.header-tab-overflow-menu')
    const nodes = Array.from(bar.childNodes)
    const tabs = nodes.filter((node) => node.nodeType === Node.ELEMENT_NODE && node.classList.contains('header-tab'))

    let lastRowWidth = null
    let frame = null

    const restore = () => {
        if (!menu.firstElementChild) return

        tabs.forEach((tab) => {
            tab.classList.remove('dropdown-item')
            tab.removeAttribute('role')
            tab.removeAttribute('tabindex')
        })
        nodes.forEach((node) => bar.appendChild(node))
    }

    const moveToMenu = (tab) => {
        tab.classList.add('dropdown-item')
        tab.setAttribute('role', 'menuitem')
        tab.setAttribute('tabindex', '-1')
        menu.appendChild(tab)
    }

    const fit = () => {
        restore()
        overflow.hidden = true
        overflow.classList.remove('active')

        const candidates = tabs.filter(isVisible)
        const widths = candidates.map((tab) => tab.getBoundingClientRect().width)
        const required = widths.reduce((sum, width) => sum + width, 0)

        const available = bar.clientWidth
        if (required <= available + WIDTH_TOLERANCE) return

        overflow.hidden = false
        const budget = available - overflow.getBoundingClientRect().width + WIDTH_TOLERANCE
        let used = 0
        let visible = 0
        while (visible < widths.length && used + widths[visible] <= budget) {
            used += widths[visible]
            visible += 1
        }

        const moved = candidates.slice(visible)
        if (moved.length === 0) {
            overflow.hidden = true
            return
        }

        moved.forEach(moveToMenu)
        overflow.classList.toggle('active', moved.some(isActive))
    }

    const schedule = () => {
        if (frame !== null) return
        frame = window.requestAnimationFrame(() => {
            frame = null
            fit()
            lastRowWidth = row.clientWidth
        })
    }

    return {
        start: () => {
            schedule()

            if (typeof ResizeObserver === 'function') {
                const observer = new ResizeObserver(() => {
                    if (row.clientWidth === lastRowWidth) return
                    schedule()
                })
                observer.observe(row)
            }

            window.addEventListener('resize', schedule)

            if (document.fonts) {
                document.fonts.ready.then(schedule)
            }
        },
    }
}

const initHeaderNavOverflow = () => {
    document.querySelectorAll('.presale-sticky-tabs').forEach((row) => {
        const bar = row.querySelector('.presale-tabs-scroll')
        const overflow = row.querySelector('.header-tab-overflow')
        if (!bar || !overflow) return

        bar.classList.add('has-overflow-menu')
        createOverflowNav(row, bar, overflow).start()
    })
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHeaderNavOverflow)
} else {
    initHeaderNavOverflow()
}

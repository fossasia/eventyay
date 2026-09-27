const HEADER_TAB_ACTIVE_CLASSES = ['active', 'underline']
const HEADER_TAB_WIDTH_TOLERANCE = 1
const HEADER_TAB_FONT_WAIT_MS = 500

const isHeaderTabVisible = (element) => element.getClientRects().length > 0

const isHeaderTabActive = (element) => HEADER_TAB_ACTIVE_CLASSES.some((name) => element.classList.contains(name))

const headerTabFonts = (elements) => [...new Set(elements.map((element) => window.getComputedStyle(element).font))]

const createOverflowNav = (row, bar, overflow) => {
    const menu = overflow.querySelector('.header-tab-overflow-menu')
    const summary = overflow.querySelector('summary')
    const nodes = Array.from(bar.childNodes)
    const tabs = nodes.filter((node) => node.nodeType === Node.ELEMENT_NODE && node.classList.contains('header-tab'))

    let lastRowWidth = null
    let frame = null

    const restore = () => {
        if (!menu.firstElementChild) return

        tabs.forEach((tab) => tab.classList.remove('dropdown-item'))
        nodes.forEach((node) => bar.appendChild(node))
    }

    const moveToMenu = (tab) => {
        tab.classList.add('dropdown-item')
        menu.appendChild(tab)
    }

    const hide = () => {
        overflow.hidden = true
        overflow.open = false
    }

    const reveal = () => {
        overflow.removeAttribute('data-overflow-pending')
    }

    const fit = () => {
        restore()
        overflow.hidden = true
        overflow.classList.remove('active')

        const candidates = tabs.filter(isHeaderTabVisible)
        const widths = candidates.map((tab) => tab.getBoundingClientRect().width)
        const required = widths.reduce((sum, width) => sum + width, 0)

        const available = bar.clientWidth
        if (required <= available + HEADER_TAB_WIDTH_TOLERANCE) {
            hide()
            return
        }

        overflow.hidden = false
        const trigger = summary || overflow
        const budget = available - trigger.getBoundingClientRect().width + HEADER_TAB_WIDTH_TOLERANCE
        let used = 0
        let visible = 0
        while (visible < widths.length && used + widths[visible] <= budget) {
            used += widths[visible]
            visible += 1
        }

        const moved = candidates.slice(visible)
        if (moved.length === 0) {
            hide()
            return
        }

        moved.forEach(moveToMenu)
        overflow.classList.toggle('active', moved.some(isHeaderTabActive))
    }

    const schedule = () => {
        if (frame !== null) return
        frame = window.requestAnimationFrame(() => {
            frame = null
            fit()
            lastRowWidth = row.clientWidth
            reveal()
        })
    }

    const watch = () => {
        if (typeof ResizeObserver === 'function') {
            const observer = new ResizeObserver(() => {
                if (row.clientWidth === lastRowWidth) return
                schedule()
            })
            observer.observe(row)
        }

        window.addEventListener('resize', schedule)
        window.addEventListener('hashchange', schedule)
        window.addEventListener('pageshow', schedule)

        if (document.fonts) {
            document.fonts.ready.then(schedule)
        }
    }

    let started = false
    const firstFit = () => {
        if (started) return
        started = true
        fit()
        lastRowWidth = row.clientWidth
        reveal()
        watch()
    }

    return {
        start: () => {
            if (!document.fonts || typeof document.fonts.check !== 'function') {
                firstFit()
                return
            }

            const icons = tabs.map((tab) => tab.querySelector('i')).filter(Boolean)
            const fonts = headerTabFonts([...tabs, ...icons])
            const fontsReady = () => fonts.every((font) => document.fonts.check(font))
            if (fontsReady()) {
                firstFit()
                return
            }

            const fitWhenReady = () => {
                if (fontsReady()) firstFit()
            }
            document.fonts.addEventListener('loadingdone', fitWhenReady)
            fonts.forEach((font) => document.fonts.load(font).then(fitWhenReady, fitWhenReady))
            window.setTimeout(firstFit, HEADER_TAB_FONT_WAIT_MS)
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

if (document.querySelector('.presale-sticky-tabs .header-tab-overflow')) {
    initHeaderNavOverflow()
} else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHeaderNavOverflow)
}

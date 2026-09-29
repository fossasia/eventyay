const HEADER_TAB_ACTIVE_CLASSES = ['active', 'underline']
const HEADER_TAB_WIDTH_TOLERANCE = 1
const HEADER_TAB_FONT_WAIT_MS = 500

const isHeaderTabVisible = (element) => element.getClientRects().length > 0

const isHeaderTabActive = (element) => HEADER_TAB_ACTIVE_CLASSES.some((name) => element.classList.contains(name))

const headerTabFonts = (elements) => [...new Set(elements.map((element) => window.getComputedStyle(element).font))]

const chooseVisibleIndexes = (widths, budget, activeIdx) => {
    let used = 0
    let visible = 0
    while (visible < widths.length && used + widths[visible] <= budget) {
        used += widths[visible]
        visible += 1
    }

    if (activeIdx < 0 || activeIdx < visible) {
        return Array.from({length: visible}, (_, i) => i)
    }

    let room = used
    let keepLeft = visible
    while (keepLeft > 0 && room + widths[activeIdx] > budget) {
        keepLeft -= 1
        room -= widths[keepLeft]
    }

    if (room + widths[activeIdx] > budget) {
        if (widths[activeIdx] <= budget) {
            return [activeIdx]
        }
        return Array.from({length: visible}, (_, i) => i)
    }

    const indexes = Array.from({length: keepLeft}, (_, i) => i)
    indexes.push(activeIdx)
    return indexes
}

const measureHeaderTabWidths = (candidates) => {
    const removed = candidates.map((tab) => {
        const active = HEADER_TAB_ACTIVE_CLASSES.filter((name) => tab.classList.contains(name))
        active.forEach((name) => tab.classList.remove(name))
        return active
    })
    const widths = candidates.map((tab) => tab.getBoundingClientRect().width)
    candidates.forEach((tab, i) => {
        removed[i].forEach((name) => tab.classList.add(name))
    })
    return widths
}

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
        const widths = measureHeaderTabWidths(candidates)
        const required = widths.reduce((sum, width) => sum + width, 0)

        const available = bar.clientWidth
        if (required <= available + HEADER_TAB_WIDTH_TOLERANCE) {
            hide()
            return
        }

        overflow.hidden = false
        const trigger = summary || overflow
        const budget = available - trigger.getBoundingClientRect().width + HEADER_TAB_WIDTH_TOLERANCE
        const activeIdx = candidates.findIndex(isHeaderTabActive)
        const keepIndexes = new Set(chooseVisibleIndexes(widths, budget, activeIdx))

        if (keepIndexes.size >= candidates.length) {
            hide()
            return
        }

        const moved = candidates.filter((_, index) => !keepIndexes.has(index))
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

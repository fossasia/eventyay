const makeCollapsed = (controller, element, collapsed) => {
    controller.setAttribute('aria-expanded', !collapsed)
    element.setAttribute('aria-hidden', collapsed)
    if (collapsed) {
        element.classList.remove('show')
    } else {
        element.classList.add('show')
    }
}


const handleCollapse = (controller, target) => {
    const wasVisible = controller.getAttribute('aria-expanded') === 'true'
    const accordion = target.getAttribute('data-parent')
    if (accordion) {
        document.querySelectorAll(`[data-parent="${accordion}"]`).forEach(element => {
            makeCollapsed(document.querySelector(`[data-target="#${element.id}"]`), element, true)
        })
    }
    makeCollapsed(controller, target, wasVisible)
}

const setupCollapse = (element) => {
    const selector = element.getAttribute('data-target')
    if (!selector) return

    // Prefer the collapse panel in the same nav-fold to avoid accidental
    // cross-targeting when IDs are reused in different sidebar sections.
    const localTarget = element.closest('.nav-fold')?.querySelector(selector)
    const target = localTarget || document.querySelector(selector)
    if (!target) return
    element.addEventListener('click', (event) => {
        event.preventDefault()
        handleCollapse(element, target)
    })
    if (target.classList.contains('show')) {
        makeCollapsed(element, target, false)
    } else {
        makeCollapsed(element, target, true)
    }
}

const initCollapse = () => {
    document.querySelectorAll('[data-toggle="collapse"]').forEach(element => {
        setupCollapse(element)
    })
}
onReady(initCollapse)

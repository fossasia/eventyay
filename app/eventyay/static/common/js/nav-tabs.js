const updateTabActiveState = () => {
    const hash = window.location.hash
    const ticketsSection = document.getElementById('tickets')
    const infoTab = document.getElementById('nav-tab-info')
    const ticketsTab = document.getElementById('nav-tab-tickets')

    if (!infoTab || !ticketsTab || !ticketsSection) return

    if (hash === '#tickets') {
        infoTab.classList.remove('active', 'underline')
        ticketsTab.classList.add('active', 'underline')
    } else {
        infoTab.classList.add('active', 'underline')
        ticketsTab.classList.remove('active', 'underline')
    }
}

const initNavTabs = () => {
    updateTabActiveState()

    window.addEventListener('hashchange', updateTabActiveState)
}

if (
    document.getElementById('nav-tab-info')
    && document.getElementById('nav-tab-tickets')
    && document.getElementById('tickets')
) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initNavTabs)
    } else {
        initNavTabs()
    }
}

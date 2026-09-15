/* Fetch-based tab navigation for Admin > Pages.
 *
 * Intercepts clicks on .pages-nav-tabs links, loads the target page via
 * fetch(), extracts the new .pages-tab-content div, swaps it in place, and
 * updates the active tab class + browser history.  The server continues to
 * render full pages; this only skips the document reload.
 *
 * Falls back to normal navigation on error or any modified click.
 */
(() => {
    const TAB_NAV = '.pages-nav-tabs';
    const CONTENT = '.pages-tab-content';
    function getContent(doc) {
        return doc.querySelector(CONTENT);
    }
    function setActiveTab(url) {
        const tabs = document.querySelectorAll(TAB_NAV + ' a');
        tabs.forEach((a) => {
            const li = a.parentElement;
            if (!li) return;
            const isSame = a.href === url || a.getAttribute('href') === url;
            li.classList.toggle('active', isSame);
        });
    }
    let inFlight = false;
    async function navigate(url, push) {
        if (inFlight) return;
        inFlight = true;
        const contentEl = document.querySelector(CONTENT);
        if (!contentEl) {
            window.location.href = url;
            return;
        }
        try {
            const response = await fetch(url, {
                method: 'GET',
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!response.ok) {
                window.location.href = url;
                return;
            }
            const html = await response.text();
            const doc = new DOMParser().parseFromString(html, 'text/html');
            const newContent = getContent(doc);
            if (!newContent) {
                window.location.href = url;
                return;
            }
            contentEl.replaceWith(newContent);
            if (window.initAllLanguageGrids) {
                window.initAllLanguageGrids();
            }
            if (window.form_handlers && window.$) {
                window.form_handlers(window.$(newContent));
            }
            if (push) {
                history.pushState({ pagesTab: url }, '', url);
            }
            setActiveTab(url);
        } catch (_err) {
            // Network error or aborted -- fall back to full navigation.
            window.location.href = url;
        } finally {
            inFlight = false;
        }
    }
    function handleClick(event) {
        // Ignore modified clicks (open in new tab etc.).
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        if (event.button !== 0) return;
        const link = event.target.closest(TAB_NAV + ' a');
        if (!link) return;
        const url = link.href;
        if (!url || link.getAttribute('target')) return;
        event.preventDefault();
        navigate(url, true);
    }
    function handlePopState(event) {
        const url = (event.state && event.state.pagesTab) || window.location.href;
        navigate(url, false);
    }
    function init() {
        if (!document.querySelector(TAB_NAV)) return;
        document.addEventListener('click', handleClick);
        window.addEventListener('popstate', handlePopState);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

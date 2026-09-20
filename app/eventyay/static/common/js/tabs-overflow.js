'use strict';

const MOVED_ATTR = 'data-tabs-overflow-moved';

const collectTabs = function(source) {
    return Array.from(source.querySelectorAll('a.header-tab')).map(function(tab) {
        return { tab: tab, parent: tab.parentNode, next: tab.nextSibling };
    });
};

const isActive = function(tab) {
    return tab.classList.contains('active') || tab.classList.contains('underline');
};

const restoreTab = function(entry) {
    entry.tab.classList.remove('dropdown-item');
    entry.tab.removeAttribute('role');
    entry.tab.removeAttribute(MOVED_ATTR);
    entry.parent.insertBefore(entry.tab, entry.next);
};

const moveTab = function(entry, target) {
    entry.tab.classList.add('dropdown-item');
    entry.tab.setAttribute('role', 'menuitem');
    entry.tab.setAttribute(MOVED_ATTR, '1');
    target.insertBefore(entry.tab, target.firstChild);
};

const overflows = function(source) {
    return source.scrollWidth > source.clientWidth + 1;
};

const layout = function(source, more, target, entries) {
    more.open = false;
    entries.slice().reverse().forEach(function(entry) {
        if (entry.tab.hasAttribute(MOVED_ATTR)) restoreTab(entry);
    });
    more.hidden = true;
    if (!overflows(source)) return;

    more.hidden = false;
    const candidates = entries.filter(function(entry) {
        return !isActive(entry.tab);
    });
    for (let i = candidates.length - 1; i >= 0 && overflows(source); i--) {
        moveTab(candidates[i], target);
    }
};

const init = function() {
    const source = document.querySelector('[data-tabs-overflow-source]');
    const more = document.querySelector('[data-tabs-overflow-more]');
    const target = more ? more.querySelector('[data-tabs-overflow-target]') : null;
    if (!source || !more || !target) return;

    const entries = collectTabs(source);
    if (!entries.length) return;

    let frame = 0;
    const schedule = function() {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(function() {
            layout(source, more, target, entries);
        });
    };

    schedule();
    window.addEventListener('resize', schedule);
    window.addEventListener('load', schedule);
    if (typeof ResizeObserver === 'function' && source.parentElement) {
        new ResizeObserver(schedule).observe(source.parentElement);
    }
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

'use strict';

const EXPANDED_CLASS = 'event-home-back--expanded';
const HOVER_MEDIA_QUERY = window.matchMedia('(hover: hover)');
const initializedLinks = new WeakSet();

const collapseExpandedLinks = function(exceptLink) {
    document.querySelectorAll(`.event-home-back.${EXPANDED_CLASS}`).forEach(function(link) {
        if (link !== exceptLink) {
            link.classList.remove(EXPANDED_CLASS);
        }
    });
};

const initEventHomeBackLink = function(link) {
    if (initializedLinks.has(link)) return;
    initializedLinks.add(link);

    link.addEventListener('click', function(event) {
        if (HOVER_MEDIA_QUERY.matches) {
            return;
        }
        if (!link.classList.contains(EXPANDED_CLASS)) {
            event.preventDefault();
            collapseExpandedLinks(link);
            link.classList.add(EXPANDED_CLASS);
        }
    });
};

const initEventHomeBack = function() {
    document.querySelectorAll('.event-home-back').forEach(initEventHomeBackLink);

    document.addEventListener('click', function(event) {
        if (event.target.closest('.event-home-back')) {
            return;
        }
        collapseExpandedLinks();
    });
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEventHomeBack);
} else {
    initEventHomeBack();
}

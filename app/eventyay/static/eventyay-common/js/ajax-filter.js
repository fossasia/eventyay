const isFilterForm = function(form) {
    const action = form.getAttribute('action');
    if (action && action.includes('/go')) {
        return false;
    }

    return form.classList.contains('filter-form') || !!form.querySelector('.filter-form') || !!form.closest('.filter-form');
};

const getFilterForms = function(root = document) {
    return Array.from(root.querySelectorAll('form')).filter(function(form) {
        return isFilterForm(form);
    });
};

const hasAjaxResultsRegion = function(root = document) {
    return !!root.querySelector('[data-ajax-results-region]');
};

let activeRequestController = null;

const getTableContainer = function(context) {
    return context.querySelector('.table-responsive') || context.querySelector('table.table') || context.querySelector('.empty-collection');
};

const getExplicitResultsRegion = function(context) {
    return context.querySelector('[data-ajax-results-region]');
};

const getResultsContainer = function(context) {
    const explicitRegion = getExplicitResultsRegion(context);
    if (explicitRegion) {
        return explicitRegion;
    }

    const tableContainer = getTableContainer(context);
    if (!tableContainer) {
        return null;
    }

    return tableContainer.closest('.tab-pane') || tableContainer;
};

const getTabContextFromForm = function(form) {
    if (!form) {
        return {
            context: document,
            tabId: null,
        };
    }

    const tabPane = form.closest('.tab-pane');
    if (!tabPane || !tabPane.id) {
        return {
            context: document,
            tabId: null,
        };
    }

    return {
        context: tabPane,
        tabId: tabPane.id,
    };
};

const reinitializeBehaviors = function(resultsContainer) {
    if (typeof window.eventyayInitTimezoneUtilities === 'function') {
        window.eventyayInitTimezoneUtilities();
    }

    if (typeof window.eventyayInitStartpageToggles === 'function') {
        window.eventyayInitStartpageToggles();
    }

    resultsContainer.dispatchEvent(new CustomEvent('eventyay:ajax-results-replaced', {
        bubbles: true,
        detail: {
            container: resultsContainer,
        },
    }));
};

const updateNextInputs = function(url, tabId) {
    const normalizedUrl = new URL(url, window.location.href);
    const nextValue = normalizedUrl.pathname + normalizedUrl.search;
    const root = tabId ? document.getElementById(tabId) : document;

    if (!root) {
        return;
    }

    root.querySelectorAll('input[name="next"]').forEach(function(input) {
        input.value = nextValue;
    });
};

const fetchAndReplace = async function(url, replaceUrlParams, form) {
    const tabContext = getTabContextFromForm(form);
    let resultsContainer = getResultsContainer(tabContext.context);
    let requestController = null;
    if (!resultsContainer) {
        window.location.href = url;
        return;
    }

    resultsContainer.style.opacity = '0.5';

    try {
        if (activeRequestController) {
            activeRequestController.abort();
        }

        requestController = new AbortController();
        activeRequestController = requestController;

        const response = await fetch(url, {
            method: 'GET',
            credentials: 'same-origin',
            signal: requestController.signal,
        });

        if (activeRequestController !== requestController) {
            return;
        }

        if (!response.ok) {
            throw new Error('Unexpected response status: ' + response.status);
        }

        const data = await response.text();
        const doc = new DOMParser().parseFromString(data, 'text/html');
        const newContext = tabContext.tabId ? doc.getElementById(tabContext.tabId) : doc;
        const newResultsContainer = newContext ? getResultsContainer(newContext) : null;

        if (!newResultsContainer) {
            window.location.href = url;
            return;
        }

        resultsContainer.replaceWith(newResultsContainer);
        resultsContainer = newResultsContainer;
        resultsContainer.style.opacity = '1';

        reinitializeBehaviors(resultsContainer);

        if (replaceUrlParams) {
            history.pushState({}, '', url);
        }

        updateNextInputs(url, tabContext.tabId);
    } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            return;
        }

        console.error('AJAX filter update failed', {
            url: url,
            error: error,
        });
        window.location.href = url;
    } finally {
        if (requestController && activeRequestController === requestController) {
            activeRequestController = null;
        }
    }
};

const buildFormUrl = function(form) {
    const url = form.getAttribute('action') || window.location.pathname;
    const query = new URLSearchParams(new FormData(form)).toString();
    if (!query) {
        return url;
    }

    return url + (url.includes('?') ? '&' : '?') + query;
};

const handleSubmit = function(event) {
    const form = event.target.closest('form');
    if (!form || !isFilterForm(form)) {
        return;
    }

    event.preventDefault();
    fetchAndReplace(buildFormUrl(form), true, form);
};

const handleClearFilter = function(event) {
    const clearButton = event.target.closest('.btn-clear-filter');
    if (!clearButton) {
        return;
    }

    const form = clearButton.closest('form');
    if (!form || !isFilterForm(form)) {
        return;
    }

    const url = clearButton.getAttribute('href');
    if (!url) {
        return;
    }

    event.preventDefault();

    form.querySelectorAll('input[type="text"], input[type="search"]').forEach(function(input) {
        input.value = '';
    });

    form.querySelectorAll('select').forEach(function(select) {
        select.value = '';
        select.dispatchEvent(new Event('change', {
            bubbles: true,
        }));
    });

    fetchAndReplace(url, true, form);
};

const handlePaginationClick = function(event) {
    const paginationLink = event.target.closest('.pagination-container a, .pagination a');
    if (!paginationLink) {
        return;
    }

    const url = paginationLink.getAttribute('href');
    if (!url || url === '#') {
        return;
    }

    event.preventDefault();

    const tabPane = paginationLink.closest('.tab-pane');
    const formInTab = tabPane ? tabPane.querySelector('form') : null;
    const defaultForm = getFilterForms()[0] || null;
    fetchAndReplace(url, true, formInTab || defaultForm);
};

const handlePopState = function() {
    const url = new URL(window.location.href, window.location.origin);
    const tabParam = url.searchParams.get('tab');
    const tabPane = tabParam ? document.getElementById(tabParam) : null;
    const activeTab = tabPane || document.querySelector('.tab-pane.active');
    const form = activeTab ? activeTab.querySelector('form') : getFilterForms()[0] || null;

    fetchAndReplace(window.location.href, false, form);
};

const initAjaxFilter = function() {
    if (!getFilterForms().length && !hasAjaxResultsRegion()) {
        return;
    }

    document.addEventListener('submit', handleSubmit);
    document.addEventListener('click', handleClearFilter);
    document.addEventListener('click', handlePaginationClick);
    window.addEventListener('popstate', handlePopState);
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAjaxFilter);
} else {
    initAjaxFilter();
}

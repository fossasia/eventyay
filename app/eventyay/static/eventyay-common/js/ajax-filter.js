$(function() {
    // Find the relevant forms, excluding those that explicitly redirect (like /go forms)
    function isFilterForm($form) {
        var action = $form.attr('action');
        if (action && action.indexOf('/go') !== -1) {
            return false;
        }
        return $form.hasClass('filter-form') || $form.find('.filter-form').length > 0 || $form.closest('.filter-form').length > 0;
    }

    function getFilterForms() {
        return $('form').filter(function() {
            return isFilterForm($(this));
        });
    }

    if (getFilterForms().length === 0) {
        return;
    }

    // Helper to find the base table/empty container within a context
    function getTableContainer($context) {
        var $container = $context.find('.table-responsive').first();
        if ($container.length === 0) {
            $container = $context.find('table.table').first();
        }
        if ($container.length === 0) {
            $container = $context.find('.empty-collection').first();
        }
        return $container;
    }

    // Helper to find the results container (table/empty state + related controls)
    function getResultsContainer($context) {
        var $tableContainer = getTableContainer($context);
        if ($tableContainer.length === 0) {
            return $tableContainer;
        }

        var $tabPane = $tableContainer.closest('.tab-pane');
        if ($tabPane.length) {
            return $tabPane;
        }

        var $parentWithPagination = $tableContainer.parents().filter(function() {
            var $el = $(this);
            if ($el.is('body') || $el.is('html')) {
                return false;
            }
            var hasResults = $el.find('.table-responsive, table.table, .empty-collection').length > 0;
            var hasPagination = $el.find('.pagination-container, .pagination').length > 0;
            return hasResults && hasPagination;
        }).first();

        if ($parentWithPagination.length) {
            return $parentWithPagination;
        }

        return $tableContainer.parent();
    }

    function fetchAndReplace(url, replaceUrlParams, $form) {
        // Scope replacements to the current tab if one exists
        var $context = $(document);
        var selectorPrefix = '';
        if ($form && $form.closest('.tab-pane').length > 0) {
            var tabId = $form.closest('.tab-pane').attr('id');
            if (tabId) {
                selectorPrefix = '#' + tabId + ' ';
                $context = $('#' + tabId);
            }
        }

        var $resultsContainer = getResultsContainer($context);
        if ($resultsContainer.length === 0) {
            window.location.href = url; // Fallback if no container found
            return;
        }

        $resultsContainer.css('opacity', '0.5');

        $.ajax({
            url: url,
            type: 'GET',
            success: function(data) {
                var doc = new DOMParser().parseFromString(data, 'text/html');
                var $newDoc = $(doc);
                
                var $newContext = selectorPrefix ? $newDoc.find(selectorPrefix) : $newDoc;
                var $newResultsContainer = getResultsContainer($newContext);

                if ($newResultsContainer.length) {
                    $resultsContainer.replaceWith($newResultsContainer);
                    $resultsContainer = $newResultsContainer; // Update reference
                }

                $resultsContainer.css('opacity', '1');

                if (window.eventyayInitTimezoneUtilities) {
                    window.eventyayInitTimezoneUtilities();
                }
                if (window.eventyayInitStartpageToggles) {
                    window.eventyayInitStartpageToggles();
                }

                if (replaceUrlParams) {
                    history.pushState({}, '', url);
                }
                var normalizedUrl = new URL(url, window.location.href);
                $context.find('input[name="next"]').val(normalizedUrl.pathname + normalizedUrl.search);
            },
            error: function() {
                // Fallback: reload page
                window.location.href = url;
            }
        });
    }

    // Intercept form submit
    $(document).on('submit', 'form', function(e) {
        var $form = $(this);
        if (!isFilterForm($form)) {
            return;
        }
        e.preventDefault();
        var url = $form.attr('action') || window.location.pathname;
        var query = $form.serialize();
        var fullUrl = url + (url.indexOf('?') !== -1 ? '&' : '?') + query;
        fetchAndReplace(fullUrl, true, $form);
    });

    // Intercept clear button
    $(document).on('click', '.btn-clear-filter', function(e) {
        var $btn = $(this);
        var $form = $btn.closest('form');
        if (!isFilterForm($form)) {
            return;
        }
        e.preventDefault();
        var url = $btn.attr('href');
        if (url) {
            $form.find('input[type="text"], input[type="search"]').val('');
            $form.find('select').val('').trigger('change');
            fetchAndReplace(url, true, $form);
        }
    });

    // Intercept pagination clicks
    $(document).on('click', '.pagination-container a, .pagination a', function(e) {
        e.preventDefault();
        var $btn = $(this);
        var url = $btn.attr('href');
        if (url && url !== '#') {
            // Find which form context this pagination belongs to
            var $form = $btn.closest('.tab-pane').find('form').first();
            if ($form.length === 0) {
                $form = getFilterForms().first();
            }
            fetchAndReplace(url, true, $form);
        }
    });
    
    // Handle back/forward navigation
    $(window).on('popstate', function() {
        var $activeTab = $('.tab-pane.active');
        var $form = $activeTab.length ? $activeTab.find('form').first() : getFilterForms().first();
        fetchAndReplace(window.location.href, false, $form);
    });
});

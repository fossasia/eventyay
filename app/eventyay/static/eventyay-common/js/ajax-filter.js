$(function() {
    // Find the relevant forms, excluding those that explicitly redirect (like /go forms)
    var $forms = $('form').filter(function() {
        var action = $(this).attr('action');
        if (action && action.indexOf('/go') !== -1) {
            return false;
        }
        return $(this).hasClass('filter-form') || $(this).find('.filter-form').length > 0 || $(this).closest('.filter-form').length > 0;
    });

    if ($forms.length === 0) {
        return;
    }

    // Helper to find the container within a context
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

        var $tableContainer = getTableContainer($context);
        if ($tableContainer.length === 0) {
            window.location.href = url; // Fallback if no container found
            return;
        }

        var $paginationContainer = $context.find('.pagination-container').first();
        
        $tableContainer.css('opacity', '0.5');
        if ($paginationContainer.length) {
            $paginationContainer.css('opacity', '0.5');
        }

        $.ajax({
            url: url,
            type: 'GET',
            success: function(data) {
                var doc = new DOMParser().parseFromString(data, 'text/html');
                var $newDoc = $(doc);
                
                var $newContext = selectorPrefix ? $newDoc.find(selectorPrefix) : $newDoc;
                var newTableContainer = getTableContainer($newContext);

                if (newTableContainer.length) {
                    $tableContainer.replaceWith(newTableContainer);
                    $tableContainer = newTableContainer; // Update reference
                }

                // Replace pagination content or remove it if none exists
                var newPaginationContainer = $newContext.find('.pagination-container').first();
                $paginationContainer = $context.find('.pagination-container').first(); // re-query in case it changed
                
                if (newPaginationContainer.length) {
                    if ($paginationContainer.length) {
                        $paginationContainer.replaceWith(newPaginationContainer);
                    } else {
                        // Insert after the table container if pagination was added
                        $tableContainer.after(newPaginationContainer);
                    }
                } else if ($paginationContainer.length) {
                    $paginationContainer.remove();
                }

                $tableContainer.css('opacity', '1');
                if ($context.find('.pagination-container').length) {
                    $context.find('.pagination-container').css('opacity', '1');
                }

                if (replaceUrlParams) {
                    history.pushState({}, '', url);
                }
                var normalizedUrl = new URL(url, window.location.origin);
                $context.find('input[name="next"]').val(normalizedUrl.pathname + normalizedUrl.search);
            },
            error: function() {
                // Fallback: reload page
                window.location.href = url;
            }
        });
    }

    // Intercept form submit
    $forms.on('submit', function(e) {
        e.preventDefault();
        var $form = $(this);
        var url = $form.attr('action') || window.location.pathname;
        var query = $form.serialize();
        var fullUrl = url + (url.indexOf('?') !== -1 ? '&' : '?') + query;
        fetchAndReplace(fullUrl, true, $form);
    });

    // Intercept clear button
    $forms.on('click', '.btn-clear-filter', function(e) {
        e.preventDefault();
        var $btn = $(this);
        var $form = $btn.closest('form');
        var url = $btn.attr('href');
        if (url) {
            $form.find('input[type="text"], input[type="search"]').val('');
            $form.find('select').val('').trigger('change');
            fetchAndReplace(url, true, $form);
        }
    });

    // Intercept pagination clicks
    $(document).on('click', '.pagination-container a', function(e) {
        e.preventDefault();
        var $btn = $(this);
        var url = $btn.attr('href');
        if (url && url !== '#') {
            // Find which form context this pagination belongs to
            var $form = $btn.closest('.tab-pane').find('form').first();
            if ($form.length === 0) {
                $form = $forms.first();
            }
            fetchAndReplace(url, true, $form);
        }
    });
    
    // Handle back/forward navigation
    $(window).on('popstate', function() {
        var $activeTab = $('.tab-pane.active');
        var $form = $activeTab.length ? $activeTab.find('form').first() : $forms.first();
        fetchAndReplace(window.location.href, false, $form);
    });
});

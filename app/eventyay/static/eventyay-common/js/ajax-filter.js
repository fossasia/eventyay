$(function() {
    // Find the relevant form
    var $form = $('form').filter(function() {
        return $(this).hasClass('filter-form') || $(this).find('.filter-form').length > 0 || $(this).closest('.filter-form').length > 0;
    }).first();

    // Find the target table or container
    var $tableContainer = $('.table-responsive');
    if ($tableContainer.length === 0) {
        $tableContainer = $('table.table').first();
    }

    if ($form.length === 0 || $tableContainer.length === 0) {
        return;
    }

    function fetchAndReplace(url, replaceUrlParams) {
        var $paginationContainer = $('.pagination');
        
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
                
                // Replace table or container content
                var newTableContainer = $newDoc.find('.table-responsive');
                if (newTableContainer.length === 0) {
                    newTableContainer = $newDoc.find('table.table').first();
                }

                if (newTableContainer.length) {
                    // If we're replacing the table directly (no wrapper), use replaceWith
                    if ($tableContainer.is('table')) {
                        $tableContainer.replaceWith(newTableContainer);
                        $tableContainer = newTableContainer; // Update reference
                    } else {
                        $tableContainer.html(newTableContainer.html());
                    }
                }

                // Replace pagination content or remove it if none exists
                var newPagination = $newDoc.find('.pagination');
                $paginationContainer = $('.pagination'); // re-query in case it changed
                
                if (newPagination.length) {
                    if ($paginationContainer.length) {
                        $paginationContainer.replaceWith(newPagination);
                    } else {
                        $tableContainer.after($('<div class="pagination text-center"></div>').html(newPagination.html()));
                    }
                } else {
                    $paginationContainer.remove();
                }

                $tableContainer.css('opacity', '1');
                if ($('.pagination').length) {
                    $('.pagination').css('opacity', '1');
                }

                if (replaceUrlParams) {
                    history.pushState({}, '', url);
                }
            },
            error: function() {
                // Fallback: reload page
                window.location.href = url;
            }
        });
    }

    // Intercept form submit
    $form.on('submit', function(e) {
        e.preventDefault();
        var url = $(this).attr('action') || window.location.pathname;
        var query = $(this).serialize();
        var fullUrl = url + (url.indexOf('?') !== -1 ? '&' : '?') + query;
        fetchAndReplace(fullUrl, true);
    });

    // Intercept clear button (using document on click to catch it inside the form)
    $form.on('click', '.btn-clear-filter', function(e) {
        e.preventDefault();
        var url = $(this).attr('href');
        if (url) {
            // Also reset form fields visually
            $form.find('input[type="text"], input[type="search"]').val('');
            $form.find('select').val('').trigger('change');
            fetchAndReplace(url, true);
        }
    });

    // Intercept pagination clicks
    $(document).on('click', '.pagination a', function(e) {
        e.preventDefault();
        var url = $(this).attr('href');
        if (url && url !== '#') {
            fetchAndReplace(url, true);
        }
    });
    
    // Handle back/forward navigation
    $(window).on('popstate', function() {
        fetchAndReplace(window.location.href, false);
    });
});

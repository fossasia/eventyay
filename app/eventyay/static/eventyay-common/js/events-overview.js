$(function () {
    // When a collapse is shown, close all others
    $('.stats-list.collapse').on('show.bs.collapse', function () {
        var activeCollapses = $('.stats-list.collapse.in');
        activeCollapses.collapse('hide');
    });

    // Close open collapse when clicking outside
    $(document).on('click', function (e) {
        if ($(e.target).closest('.stats-list.collapse, .stats-dropdown-toggle').length === 0) {
            $('.stats-list.collapse.in').collapse('hide');
        }
    });
});

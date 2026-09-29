document.addEventListener('DOMContentLoaded', function() {
    const detailsElements = document.querySelectorAll('.provider-help-details');

    // Close on outside click
    document.addEventListener('click', function (e) {
        detailsElements.forEach(function (el) {
            if (el.hasAttribute('open') && !el.contains(e.target)) {
                el.removeAttribute('open');
            }
        });
    });

    // Accordion behavior: close others when one is opened
    detailsElements.forEach(function(el) {
        el.addEventListener('toggle', function(e) {
            if (el.open) {
                detailsElements.forEach(function(other) {
                    if (other !== el && other.open) {
                        other.removeAttribute('open');
                    }
                });
            }
        });
    });
});

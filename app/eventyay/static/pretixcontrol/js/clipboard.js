$(function() {
    $('.btn-clipboard').tooltip({
      trigger: 'click',
      placement: 'bottom'
    });

    function setTooltip(btn, message) {
      $(btn).tooltip('hide')
        .attr('data-original-title', message)
        .tooltip('show');
    }

    function hideTooltip(btn) {
      setTimeout(function() {
        $(btn).tooltip('hide');
      }, 1000);
    }

    var clipboard = new Clipboard('.btn-clipboard');

    clipboard.on('success', function(e) {
      if (e.text.length > 0) {
        setTooltip(e.trigger, gettext('Copied!'));
        hideTooltip(e.trigger);

        if (e.trigger.classList.contains('btn-copy-confirm')) {
          var btn = e.trigger;
          var icon = btn.querySelector('.fa');
          btn.classList.add('copied');
          if (icon) {
            icon.classList.remove('fa-copy');
            icon.classList.add('fa-check');
          }
          clearTimeout(btn._copyResetTimer);
          btn._copyResetTimer = setTimeout(function() {
            btn.classList.remove('copied');
            if (icon) {
              icon.classList.remove('fa-check');
              icon.classList.add('fa-copy');
            }
          }, 2000);
        }
      }
    });

    clipboard.on('error', function(e) {
      setTooltip(e.trigger, gettext('Press Ctrl-C to copy!'));
      hideTooltip(e.trigger);
    });
});


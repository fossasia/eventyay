/*global $ */
/*
 Based on https://github.com/BlackrockDigital/startbootstrap-sb-admin-2
 Copyright 2013-2016 Blackrock Digital LLC
 MIT License
 Modified by Raphael Michel
 */
//Loads the correct sidebar on window load,
//collapses the sidebar on window resize.
// Sets the min-height of #page-wrapper to window size
// mobile-view: collapse on outside click or link click
$(function () {
    'use strict';

    const $body = $('body');
    const $sidebar = $('.sidebar');
 toggleSidebar();    const $navbar = $('.navbar');
    const $pageWrapper = $('#page-wrapper');
    
    function getNavbarHeight() {
        return $navbar.outerHeight() || 50;
    }
    
    function updateCSSVariables() {
        document.documentElement.style.setProperty('--navbar-height', getNavbarHeight() + 'px');
    }
    const $sidebarToggleButton = $('#sidebar-toggle');
    
    function isMobileView() {
        return window.matchMedia("(max-width: 767px)").matches;
    }


    function isTabletOrDesktop() {
        return window.matchMedia("(min-width: 768px)").matches;
    }

    function toggleSidebar() {
        $body.toggleClass('sidebar-minimized');
        if (isTabletOrDesktop()) {
            localStorage.setItem('sidebar-minimized', $body.hasClass('sidebar-minimized'));
        }
    }

    function initializeSidebar() {
        $('#side-menu').metisMenu({
            toggle: false
        });

        if (isMobileView()) {
            if (!$body.hasClass('sidebar-minimized')) {
                $body.addClass('sidebar-minimized');
            }
        } else {
            if (localStorage.getItem('sidebar-minimized') === null) {
                localStorage.setItem('sidebar-minimized', 'true');
            } else if (localStorage.getItem('sidebar-minimized') === 'true') {
                if (!$body.hasClass('sidebar-minimized')) {
                    $body.addClass('sidebar-minimized');
                }
            } else {
                $body.removeClass('sidebar-minimized');
            }
        }
    }

    updateCSSVariables();
    initializeSidebar();

    $sidebarToggleButton.on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        toggleSidebar();
    });

    if ($sidebar.length) {
        $(document).on('click', function (e) {
            if (!isMobileView() || $body.hasClass('sidebar-minimized')) return;
            if ($(e.target).closest('.sidebar, #sidebar-toggle').length) return;
            $body.addClass('sidebar-minimized');
        });
        $sidebar.on('click', 'a[href]', function () {
            if (!isMobileView()) return;
            var href = ($(this).attr('href') || '').trim();
            if (!href || href.charAt(0) === '#') return;
            $body.addClass('sidebar-minimized');
        });
    }

    let resizeTimeout;
    $(window).on('resize', function () {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(function() {
            updateCSSVariables();
        }, 150);
    });

    $(window).bind("load resize", function () {
        var topOffset = getNavbarHeight();

        var height = ((this.window.innerHeight > 0) ? this.window.innerHeight : this.screen.height) - 1;
        height = height - topOffset;
        if (height < 1) height = 1;
        if (height > topOffset) {
            $("#page-wrapper").css("min-height", (height) + "px");
        }
    });

    $('ul.nav ul.nav-second-level a.active').parent().parent().addClass('in').parent().addClass('active');

    var supportsOverscrollContain = (window.CSS && CSS.supports && CSS.supports('overscroll-behavior: contain'))
        || ('overscrollBehavior' in document.documentElement.style);
    if (!supportsOverscrollContain) {
        function stopPropagationHandler(e) {
            e.stopPropagation();
        }
        [$sidebar, $pageWrapper].forEach(function($el) {
            $el.on('wheel', stopPropagationHandler);
            $el.on('touchmove', stopPropagationHandler);
        });
    }
});

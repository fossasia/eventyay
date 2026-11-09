/*
 * Based on:
 * metismenu - v1.1.3
 * Easy menu jQuery plugin for Twitter Bootstrap 3
 * https://github.com/onokumus/metisMenu
 *
 * Made by Osman Nuri Okumus
 * Under MIT License
 * Modified by Raphael Michel
 */
;(function($, window, document, undefined) {

    var pluginName = "metisMenu",
        defaults = {
            toggle: true,
        };

    function Plugin(element, options) {
        this.element = $(element);
        this.settings = $.extend({}, defaults, options);
        this._defaults = defaults;
        this._name = pluginName;
        this.init();
    }

    Plugin.prototype = {
        init: function() {

            var $this = this.element,
                $toggle = this.settings.toggle,
                obj = this;

            if (this.isIE() <= 9) {
                $this.find("li.active").has("ul").children("ul").collapse("show");
                $this.find("li").not(".active").has("ul").children("ul").collapse("hide");
            } else {
                $this.find("li.active").has("ul").children("ul").addClass("collapse in");
                $this.find("li").not(".active").has("ul").children("ul").addClass("collapse");
            }

            $this.find("li").has("ul").children("a.arrow").on("click" + "." + pluginName, function(e) {
                e.preventDefault();
                $(this).blur();

                // Toggle the classes directly instead of Bootstrap's animated collapse, so the
                // submenu opens instantly and stays in sync with the parent's "active" state.
                var item = this.parentElement;
                var isActive = item.classList.toggle("active");
                var submenu = item.querySelector(":scope > ul");
                if (submenu) {
                    submenu.classList.toggle("in", isActive);
                }

                if ($toggle) {
                    Array.prototype.forEach.call(item.parentElement.children, function(sibling) {
                        if (sibling === item) return;
                        sibling.classList.remove("active");
                        var openSubmenu = sibling.querySelector(":scope > ul.in");
                        if (openSubmenu) {
                            openSubmenu.classList.remove("in");
                        }
                    });
                }

            });
        },

        isIE: function() { //https://gist.github.com/padolsey/527683
            var undef,
                v = 3,
                div = document.createElement("div"),
                all = div.getElementsByTagName("i");

            while (
                div.innerHTML = "<!--[if gt IE " + (++v) + "]><i></i><![endif]-->",
                all[0]
            ) {
                return v > 4 ? v : undef;
            }
        },

        remove: function() {
            this.element.off("." + pluginName);
            this.element.removeData(pluginName);
        }

    };

    $.fn[pluginName] = function(options) {
        this.each(function () {
            var el = $(this);
            if (el.data(pluginName)) {
                el.data(pluginName).remove();
            }
            el.data(pluginName, new Plugin(this, options));
        });
        return this;
    };

})(jQuery, window, document);